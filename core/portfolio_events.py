"""#8b — Auto-detect dividends / splits / bonus issues for held stocks.

Source: Downstox NSE corporate-announcements feed (recent items only).
Detection is strictly advisory: suggestions are returned with a stable id so
they can be dismissed, and applying one always goes through the existing
manual endpoints (dividend / corp-action) with user confirmation. Nothing in
the portfolio is ever mutated automatically.
"""

import hashlib
import re
from typing import Optional

from core.downstox import get_announcements
from core.portfolio import PORTFOLIO_FILE, _load_json, get_dismissed_events, add_dismissed_event

# Keyword patterns per event type, checked against subject + category.
_DIV_AMOUNT_RE = re.compile(
    r"(?:rs\.?|₹|inr)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:per\s+(?:share|equity)|/-)",
    re.IGNORECASE,
)
# Fallback: "5.50 per share" without the currency marker.
_DIV_AMOUNT_RE2 = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*per\s+share", re.IGNORECASE)
_RATIO_RE = re.compile(r"(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)")
# "sub-division ... from Rs 10 to Rs 2" -> ratio 5 (face-value based splits).
_FV_RE = re.compile(r"(?:from|rs\.?)\s*(?:rs\.?|₹)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:to|-)\s*(?:rs\.?|₹)?\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)


def _base_symbol(symbol: str) -> str:
    """NTPC.NS -> NTPC (announcement symbols carry no exchange suffix)."""
    return (symbol or "").split(".")[0].upper().strip()


def _parse_ratio(text: str, kind: str) -> Optional[float]:
    """New-shares-per-old-share ratio for split/bonus texts. Best effort."""
    if kind == "split":
        # Face-value phrasing wins when present: 10 -> 2 means 1 becomes 5.
        m = _FV_RE.search(text)
        if m:
            try:
                old, new = float(m.group(1)), float(m.group(2))
                if old > 0 and new > 0 and old > new:
                    return round(old / new, 6)
            except ValueError:
                pass
        m = _RATIO_RE.search(text)
        if m:
            try:
                old, new = float(m.group(1)), float(m.group(2))
                if old > 0 and new > 0:
                    return round(new / old, 6)
            except ValueError:
                pass
    else:  # bonus — "1:2" means two new for every one held
        m = _RATIO_RE.search(text)
        if m:
            try:
                old, new = float(m.group(1)), float(m.group(2))
                if old > 0 and new > 0:
                    return round(new / old, 6)
            except ValueError:
                pass
    return None


def _classify(subject: str, category: str) -> Optional[dict]:
    text = f"{subject} {category}"
    low = text.lower()
    if "dividend" in low:
        m = _DIV_AMOUNT_RE.search(text) or _DIV_AMOUNT_RE2.search(subject)
        return {"type": "dividend", "perShare": float(m.group(1)) if m else None}
    if "split" in low or "sub-divis" in low or "sub divis" in low:
        return {"type": "split", "perShare": None}
    if "bonus" in low and "issue" in low or "bonus shares" in low or ("bonus" in low and "equity" in low):
        return {"type": "bonus", "perShare": None}
    return None


def _event_id(ann: dict) -> str:
    raw = "|".join(str(ann.get(k, "")) for k in ("exchange", "symbol", "publishedAt", "subject"))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def get_portfolio_event_suggestions() -> dict:
    """Suggested dividend / split / bonus events for current holdings."""
    holdings = _load_json(PORTFOLIO_FILE).get("holdings", [])
    if not holdings:
        return {"suggestions": [], "count": 0, "source": "downstox"}

    qty_by_base = {}
    symbol_by_base = {}
    for holding in holdings:
        base = _base_symbol(holding.get("symbol", ""))
        qty_by_base[base] = float(holding.get("quantity", 0) or 0)
        symbol_by_base[base] = holding.get("symbol", "")

    dismissed = set(get_dismissed_events())
    suggestions = []
    for ann in get_announcements():
        base = _base_symbol(ann.get("symbol", ""))
        if base not in qty_by_base:
            continue
        hit = _classify(str(ann.get("subject", "")), str(ann.get("category", "")))
        if not hit:
            continue
        event_id = _event_id(ann)
        if event_id in dismissed:
            continue

        per_share = hit.get("perShare")
        quantity = qty_by_base[base]
        suggestion = {
            "id": event_id,
            "symbol": base,
            "holdingSymbol": symbol_by_base[base],
            "type": hit["type"],
            "category": ann.get("category", ""),
            "subject": ann.get("subject", ""),
            "company": ann.get("company", ""),
            "publishedAt": ann.get("publishedAt", ""),
            "perShare": per_share,
            "suggestedAmount": round(per_share * quantity, 2) if per_share and quantity else None,
            "quantity": quantity,
            "ratio": None,
            "pdfUrl": ann.get("pdfUrl", ""),
        }
        if hit["type"] in ("split", "bonus"):
            suggestion["ratio"] = _parse_ratio(str(ann.get("subject", "")), hit["type"])
        suggestions.append(suggestion)

    suggestions.sort(key=lambda s: s.get("publishedAt") or "", reverse=True)
    return {"suggestions": suggestions, "count": len(suggestions), "source": "downstox"}


def dismiss_event(event_id: str) -> dict:
    if not event_id:
        return {"error": "Missing event id"}
    return add_dismissed_event(event_id)
