"""News Monitor API (port of trader-news from Indian Day Trader).

Aggregates Google News India RSS, NSE Corporate Announcements, and price moves
for Indian stocks. Categorizes by topic (earnings, regulatory, deal, management,
general) and deduplicates. Advisory only — headlines are leads, not facts.

Endpoints:
  GET  /api/news          Aggregated news for watchlist symbols
  POST /api/news/check    Check news and return new items since last check
"""

from __future__ import annotations

import datetime
import email.utils
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from core.trader_core import IST

router = APIRouter(prefix="/api/news", tags=["news"])

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
NEWS_STATE_FILE = os.path.join(DATA_DIR, "news_state.json")

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30), name="IST")

YAHOO_INDIA_RSS = "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%s&region=IN&lang=en-IN"
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q=%s&hl=en-IN&gl=IN&ceid=IN:en"
NSE_ANNOUNCEMENTS = "https://www.nseindia.com/api/corporate-announcements?index=equities&symbol=%s"

UA = "Mozilla/5.0 (compatible; day-trader-skill/2.0; +https://github.com/Jakeschincariol/day-trader-skill)"
KEEP_DAYS = 30
MOVE_PCT = 3.0

TOPIC_PATTERNS = {
    "earnings": re.compile(
        r"\b(?:earnings|results|quarterly|profit|revenue|ebitda|pat|dividend|interim dividend|"
        r"q[1-4]\b|financial results|net profit|eps|income|gross margin|operating profit)\b",
        re.I,
    ),
    "regulatory": re.compile(
        r"\b(?:sebi|regulatory|regulator|circular|penalty|probe|investigation|show cause|"
        r"sat\b|tribunal|ed\b|enforcement directorate|cbi\b|rbi\b|cci\b|compliance|"
        r"notice|adjudication|debar|insider trading|pit\b|lodr|order)\b",
        re.I,
    ),
    "deal": re.compile(
        r"\b(?:acqui(?:re|res|red|sition)|merger|buyout|takeover|deal|stake|"
        r"joint venture|jv\b|open offer|divestment|block deal|bulk deal|amalgamation)\b",
        re.I,
    ),
    "management": re.compile(
        r"\b(?:ceo\b|cfo\b|md\b|managing director|executive director|chairman|chairperson|"
        r"appointment|appoints?|appointed|resigns?|resignation|steps? down|stepped down|"
        r"board|director|kmp|senior management)\b",
        re.I,
    ),
}


class NewsError(Exception):
    pass


class NewsCheckRequest(BaseModel):
    tickers: Optional[List[str]] = None
    hours: float = 48
    show_all: bool = False


class NewsCheckResponse(BaseModel):
    checked: str
    updated_at: str
    timezone: str
    moves: List[dict]
    items: List[dict]
    notes: List[str]


def _parse_time(value: Any) -> Optional[datetime.datetime]:
    """RFC 822 (RSS), ISO 8601, or Indian exchange format -> aware UTC datetime."""
    value = (value or "").strip()
    if not value:
        return None
    d = None
    try:
        d = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        d = None
    if d is None:
        try:
            d = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    if d is None:
        for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
            try:
                naive = datetime.datetime.strptime(value, fmt)
                d = naive.replace(tzinfo=IST)
                break
            except ValueError:
                continue
    if d is None:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=datetime.timezone.utc)
    return d.astimezone(datetime.timezone.utc)


def _yahoo_symbol(ticker: str) -> str:
    t = ticker.upper().strip().replace("-", ".")
    if t.endswith(".NS") or t.endswith(".BO"):
        return t
    return t + ".NS"


def _build_google_news_url(ticker: str, company_name: Optional[str] = None) -> str:
    raw_sym = ticker.split(".")[0].strip()
    if company_name and len(company_name) >= 3:
        q = '%s OR "%s"' % (raw_sym, company_name.strip())
    else:
        q = raw_sym
    encoded_q = urllib.parse.quote(q)
    return GOOGLE_NEWS_RSS % encoded_q


def _sanitize_text(text: str, max_len: int = 300) -> str:
    if not text:
        return ""
    clean = re.sub(r"[\x00-\x1f\x7f-\x9f]+", " ", str(text))
    clean = re.sub(r"<[^>]+>", " ", clean)
    clean = " ".join(clean.split())
    if len(clean) > max_len:
        clean = clean[:max_len].rsplit(" ", 1)[0]
    return clean.strip()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(el: Any, name: str) -> str:
    for c in el.iter():
        if _local(c.tag) == name:
            return (c.text or "").strip()
    return ""


def _safe_fromstring(data: bytes, ticker: str, label: str = "XML") -> Any:
    if not isinstance(data, (bytes, bytearray)):
        data = data.encode("utf-8")
    if b"<!ENTITY" in data or (b"<!DOCTYPE" in data and (b"SYSTEM" in data or b"PUBLIC" in data)):
        raise NewsError(f"{label} for {ticker} contains disallowed XML entity declarations")
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise NewsError(f"{label} for {ticker} is not valid XML: {exc}")


def _parse_google_rss(data: bytes, ticker: str) -> List[dict]:
    root = _safe_fromstring(data, ticker, "Google News RSS")
    out = []
    sym = _yahoo_symbol(ticker)
    for it in root.iter("item"):
        title = _sanitize_text(_text(it, "title"), 300)
        link = _text(it, "link")
        guid = _text(it, "guid") or link
        desc = _sanitize_text(_text(it, "description"), 500)
        source = _text(it, "source") or "Google News India"
        pub_date = _parse_time(_text(it, "pubDate"))
        out.append({
            "id": "google:" + guid,
            "source": "Google News India",
            "kind": "headline",
            "ticker": sym,
            "title": title,
            "summary": desc,
            "link": link,
            "time": pub_date.isoformat() if pub_date else None,
        })
    return out


def _parse_rss(data: bytes, ticker: str) -> List[dict]:
    root = _safe_fromstring(data, ticker, "RSS")
    out = []
    sym = _yahoo_symbol(ticker)
    for it in root.iter("item"):
        title = _sanitize_text(_text(it, "title"), 300)
        link = _text(it, "link")
        guid = _text(it, "guid") or link
        desc = _sanitize_text(_text(it, "description"), 500)
        out.append({
            "id": "rss:" + guid,
            "source": "Yahoo Finance India",
            "kind": "headline",
            "ticker": sym,
            "title": title,
            "summary": desc,
            "link": link,
            "time": _parse_time(_text(it, "pubDate")).isoformat() if _parse_time(_text(it, "pubDate")) else None,
        })
    return out


def _parse_nse_announcements(data: bytes, ticker: str) -> List[dict]:
    try:
        doc = json.loads(data.decode("utf-8") if isinstance(data, bytes) else data)
    except (ValueError, UnicodeDecodeError) as exc:
        raise NewsError(f"NSE announcements for {ticker} is not valid JSON: {exc}")
    entries = doc if isinstance(doc, list) else doc.get("data", [])
    out = []
    sym = _yahoo_symbol(ticker)
    for entry in entries:
        seq_id = str(entry.get("seq_id") or entry.get("id") or "")
        desc = entry.get("desc") or entry.get("sm_name") or entry.get("attchmntText") or ""
        title = _sanitize_text(desc, 300)
        dt_str = entry.get("dt") or entry.get("an_dt") or ""
        pub_time = _parse_time(dt_str)
        link = entry.get("attchmntFile") or entry.get("link") or ""
        summary = _sanitize_text(entry.get("attchmntText") or entry.get("desc") or "", 500)
        item_id = "nse:" + seq_id if seq_id else "nse:" + hashlib.sha1(title.encode("utf-8")).hexdigest()[:12]
        out.append({
            "id": item_id,
            "source": "NSE",
            "kind": "announcement",
            "ticker": sym,
            "title": title,
            "summary": summary,
            "link": link,
            "time": pub_time.isoformat() if pub_time else None,
        })
    return out


def _fetch(url: str, timeout: int = 10) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            import gzip
            data = gzip.decompress(data)
        return data


def _classify_topics(text: str) -> List[str]:
    if not text:
        return ["general"]
    clean = _sanitize_text(text, max_len=1000)
    tags = []
    if TOPIC_PATTERNS["earnings"].search(clean):
        tags.append("earnings")
    if TOPIC_PATTERNS["regulatory"].search(clean):
        tags.append("regulatory")
    if TOPIC_PATTERNS["deal"].search(clean):
        tags.append("deal")
    if TOPIC_PATTERNS["management"].search(clean):
        tags.append("management")
    if not tags:
        tags.append("general")
    return tags


def _mention_patterns(watch: Dict[str, Optional[str]]) -> Dict[str, re.Pattern]:
    pats = {}
    for t, name in watch.items():
        base = t.split(".")[0].upper()
        alts = [
            r"\(%s\)" % re.escape(t),
            r"\(%s\)" % re.escape(base),
            r"\$%s\b" % re.escape(base),
            r"\b(?:NSE|BSE)\s*:\s*%s\b" % re.escape(base),
            r"\b%s\b" % re.escape(t),
        ]
        if len(base) >= 3:
            alts.append(r"\b%s\b" % re.escape(base))
        if name and len(name) >= 3:
            clean_name = re.escape(name).replace(r"\ ", r"[\s-]")
            alts.append(r"\b%s\b" % clean_name)
        pats[t] = re.compile("|".join(alts), re.I)
    return pats


def _tag_items(items: List[dict], watch: Dict[str, Optional[str]]) -> List[dict]:
    pats = _mention_patterns(watch)
    for it in items:
        hay = "%s %s" % (it["title"], it.get("summary") or "")
        touches = set()
        if it.get("ticker") in watch:
            touches.add(it["ticker"])
        for t, rx in pats.items():
            if rx.search(hay):
                touches.add(t)
        it["touches"] = sorted(touches) if touches else [it.get("ticker", "")]
        it["tags"] = _classify_topics(hay)
        it["important"] = bool(
            "regulatory" in it["tags"] or
            ("earnings" in it["tags"] and ("net profit" in hay.lower() or "dividend" in hay.lower())) or
            it.get("kind") == "announcement"
        )
    return items


def _dedupe(items: List[dict]) -> List[dict]:
    seen, out = {}, []
    for it in items:
        norm_title = re.sub(r"\W+", " ", it["title"].lower()).strip()
        day = it["time"].strftime("%Y-%m-%d") if isinstance(it.get("time"), datetime.datetime) else ""
        keys = [it.get("id"), it.get("link"), "%s|%s" % (norm_title, day) if norm_title else ""]
        hit = next((seen[k] for k in keys if k and k in seen), None)
        if hit is not None:
            for t in it.get("touches", []):
                if t not in hit["touches"]:
                    hit["touches"].append(t)
            hit["touches"].sort()
            for tag_name in it.get("tags", []):
                if tag_name not in hit["tags"]:
                    hit["tags"].append(tag_name)
            continue
        for k in keys:
            if k:
                seen[k] = it
        out.append(it)
    return out


def _fingerprint(it: dict) -> str:
    return hashlib.sha1(it["id"].encode("utf-8")).hexdigest()[:16]


def _collect(
    watch: Dict[str, Optional[str]],
    errors: Optional[List[str]] = None,
) -> List[dict]:
    errors = [] if errors is None else errors
    items = []
    for t in sorted(watch):
        sym = _yahoo_symbol(t)
        raw_t = t.split(".")[0].upper()
        company_name = watch.get(t) or watch.get(sym) or watch.get(raw_t)

        # 1. Google News India RSS
        google_url = _build_google_news_url(raw_t, company_name)
        google_name = "google-%s.xml" % raw_t
        try:
            items += _parse_google_rss(_fetch(google_url), sym)
        except Exception as exc:
            errors.append("Google News for %s: %s" % (raw_t, exc))

        # 2. NSE Corporate Announcements
        nse_url = NSE_ANNOUNCEMENTS % raw_t
        try:
            items += _parse_nse_announcements(_fetch(nse_url), sym)
        except Exception as exc:
            errors.append("NSE announcements for %s: %s" % (raw_t, exc))

    return items


def _json_ready(items: List[dict]) -> List[dict]:
    out = []
    for it in items:
        d = dict(it)
        if isinstance(d.get("time"), datetime.datetime):
            d["time"] = d["time"].astimezone(IST).isoformat()
        out.append(d)
    return out


@router.get("")
def get_news(
    tickers: Optional[str] = Query(default=None),
    hours: float = Query(default=48),
    show_all: bool = Query(default=False),
):
    """Get aggregated news for watchlist symbols."""
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        state = _load_state()

        if tickers:
            watch = {_yahoo_symbol(t): None for t in tickers.split(",") if t.strip()}
        else:
            watch = {}

        errors = []
        items = _collect(watch, errors=errors)
        items = _tag_items(items, watch)
        items = _dedupe(items)

        cutoff = now - datetime.timedelta(hours=hours)
        ahead = now + datetime.timedelta(minutes=10)
        seen = state.setdefault("seen", {})
        out = []
        for it in items:
            it_time = it.get("time")
            if isinstance(it_time, str):
                it_time = _parse_time(it_time)
            if it_time is not None and (it_time < cutoff or it_time > ahead):
                continue
            fp = _fingerprint(it)
            it["new"] = fp not in seen
            if it["new"] or show_all:
                out.append(it)
        out.sort(key=lambda i: (i.get("time") or now), reverse=True)

        # Price moves (placeholder - no live price fetch in news endpoint)
        moves = []

        result = {
            "checked": now.astimezone(IST).isoformat(),
            "updated_at": now.astimezone(IST).isoformat(),
            "timezone": "IST",
            "moves": moves,
            "items": _json_ready(out),
            "notes": errors,
        }
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check", response_model=NewsCheckResponse)
def check_news(req: NewsCheckRequest):
    """Check news and return new items since last check."""
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        state = _load_state()

        if req.tickers:
            watch = {_yahoo_symbol(t): None for t in req.tickers}
        else:
            watch = {}

        errors = []
        items = _collect(watch, errors=errors)
        items = _tag_items(items, watch)
        items = _dedupe(items)

        cutoff = now - datetime.timedelta(hours=req.hours)
        ahead = now + datetime.timedelta(minutes=10)
        seen = state.setdefault("seen", {})
        out = []
        for it in items:
            it_time = it.get("time")
            if isinstance(it_time, str):
                it_time = _parse_time(it_time)
            if it_time is not None and (it_time < cutoff or it_time > ahead):
                continue
            fp = _fingerprint(it)
            it["new"] = fp not in seen
            if it["new"] or req.show_all:
                out.append(it)
        out.sort(key=lambda i: (i.get("time") or now), reverse=True)

        moves = []

        # Remember seen items
        stamp = now.isoformat()
        for it in items:
            seen.setdefault(_fingerprint(it), stamp)
        state["seen"] = {
            k: v for k, v in seen.items()
            if v >= (now - datetime.timedelta(days=KEEP_DAYS)).isoformat()
        }
        state["last_check"] = stamp
        _save_state(state)

        return {
            "checked": now.astimezone(IST).isoformat(),
            "updated_at": now.astimezone(IST).isoformat(),
            "timezone": "IST",
            "moves": moves,
            "items": _json_ready(out),
            "notes": errors,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _load_state() -> dict:
    if not os.path.exists(NEWS_STATE_FILE):
        return {}
    try:
        with open(NEWS_STATE_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (ValueError, OSError):
        return {}


def _save_state(state: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = NEWS_STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, NEWS_STATE_FILE)
