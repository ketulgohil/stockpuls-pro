"""Daily portfolio recommendation scans.

Extends the original daily scan (weekdays 15:45 IST after NSE close) with:

* Immutable persistence — every scan appends one record per symbol per horizon
  into SQLite (``core.recommendation_store``, migration v2). Nothing is
  overwritten; ``data/portfolio.json`` no longer stores generated
  recommendations (the database is the single source of truth).
* Daily/swing vs intraday separation — the daily record comes from
  ``core.signals.generate_signals`` (RSI/MACD/Bollinger/SMA-cross/MFI over
  ~6 months of daily Upstox candles); the intraday record comes from
  ``core.intraday.signals.ConfluenceSignalEngine`` (VWAP/EMA/RSI/volume
  confluence, 0-100, qualified >= 80) over the live engine's 5m candles.
  They are stored with different ``horizon`` values and never merged.
* Honest data states — NO_DATA (provider returned nothing / errored),
  NOT_ENOUGH_DATA (< 60 daily candles), plus the data "as of" date and a
  staleness flag when the provider's last candle predates the scan day.
* Holiday awareness via the NSE calendar in ``core.trader_core.calendar``.
  NOTE: the bundled calendar lists NSE holidays for 2026 only; beyond that
  weekend-only filtering applies and the limitation is surfaced in the UI.

Aggregation rule (deterministic, documented in the UI):
  buy_score  = sum(2 for Strong BUY signals, 1 for Moderate)
  sell_score = sum(2 for Strong SELL signals, 1 for Moderate)
  BUY if buy_score > sell_score, SELL if sell_score > buy_score,
  otherwise HOLD (includes ties and "no signals fired").

Recommendations are informational only — no broker orders are ever placed and
holding quantities/cash are never mutated.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time as time_module
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from core.portfolio import PORTFOLIO_FILE, _load_json
from core.signals import generate_signals
from core.data_fetcher import get_stock_data
from core.recommendation_store import get_store
from core.trader_core import is_trading_day

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")
SCAN_TIME = time(15, 45)  # after the regular NSE session (15:30 close)

MIN_DAILY_CANDLES = 60
STRATEGY_NAME = "tech_signals_vote"
INTRADAY_STRATEGY_NAME = "intraday_confluence"
STRATEGY_VERSION = "1.0"
MANUAL_RESCAN_COOLDOWN_SEC = 600

_scan_lock = threading.Lock()
_last_rescan_monotonic: Optional[float] = None
_last_eval_monotonic = 0.0
EVALUATION_RETRY_INTERVAL_SEC = 1800


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
def aggregate_signals(signals: List[Dict[str, Any]]) -> Tuple[str, float, float]:
    """Weighted vote over existing technical signals -> (label, buy, sell)."""
    buy_score = sum(2 if s.get("strength") == "Strong" else 1
                    for s in signals if s.get("type") == "BUY")
    sell_score = sum(2 if s.get("strength") == "Strong" else 1
                     for s in signals if s.get("type") == "SELL")
    if buy_score > sell_score:
        decision = "BUY"
    elif sell_score > buy_score:
        decision = "SELL"
    else:
        decision = "HOLD"
    return decision, float(buy_score), float(sell_score)


def _daily_recommendation(symbol: str) -> Dict[str, Any]:
    """One daily/swing record from historical daily data (no live state)."""
    try:
        history = get_stock_data(symbol, period="6mo")
    except Exception:
        logger.exception("Portfolio signal scan failed for %s", symbol)
        return {"recommendation": "NO_DATA", "signals": [], "note": "Data provider error"}

    if history is None or getattr(history, "empty", True):
        return {"recommendation": "NO_DATA", "signals": [], "note": "Provider returned no candles"}

    try:
        signals = generate_signals(symbol)
    except Exception:
        logger.exception("Signal generation failed for %s", symbol)
        return {"recommendation": "NO_DATA", "signals": [], "note": "Signal engine error"}

    candle_count = len(history)
    if candle_count < MIN_DAILY_CANDLES:
        return {
            "recommendation": "NOT_ENOUGH_DATA",
            "signals": signals,
            "note": f"Only {candle_count} daily candles available (< {MIN_DAILY_CANDLES})",
        }

    decision, buy_score, sell_score = aggregate_signals(signals)
    try:
        last_row = history.iloc[-1]
        reference_price = float(last_row["Close"])
        data_as_of = str(history.index[-1])[:10]
    except (KeyError, IndexError, TypeError, ValueError):
        return {"recommendation": "NO_DATA", "signals": [], "note": "Malformed candle data"}

    return {
        "recommendation": decision,
        "signals": signals,
        "buy_score": buy_score,
        "sell_score": sell_score,
        "reference_price": reference_price,
        "reference_date": data_as_of,
        "data_as_of": data_as_of,
    }


def _intraday_recommendation(symbol: str) -> Dict[str, Any]:
    """One intraday record from the live engine's 5m candles (clearly a
    different horizon; generated only when intraday data actually exists)."""
    clean = symbol.upper().replace(".NS", "").replace(".BO", "").strip()
    try:
        from core.intraday.signals import ConfluenceSignalEngine
        from core.upstox.stream import upstox_engine
        candles = upstox_engine.get_5m_candles(clean)
        if candles is None:
            return {"recommendation": "NO_DATA",
                    "signals": [],
                    "note": "Live engine unavailable"}
        if len(candles) < 20:
            return {"recommendation": "NOT_ENOUGH_DATA",
                    "signals": [],
                    "note": f"Only {len(candles)} intraday candles available (< 20)"}
        result = ConfluenceSignalEngine().evaluate(clean, engine=upstox_engine)
    except Exception:
        logger.exception("Intraday evaluation failed for %s", symbol)
        return {"recommendation": "NO_DATA", "signals": [], "note": "Live engine unavailable"}

    if not result:
        return {"recommendation": "NOT_ENOUGH_DATA",
                "signals": [],
                "note": "Intraday indicators could not be computed"}

    factors = result.get("factors") or {}
    signal_rows = [
        {"indicator": name, "type": "BUY" if met else "NEUTRAL",
         "strength": "Strong" if met else "Moderate",
         "message": name.replace("_", " ")}
        for name, met in factors.items()
    ]
    score = float(result.get("confluence_score") or 0)
    return {
        "recommendation": "BUY" if result.get("qualified") else "NONE",
        "signals": signal_rows,
        "buy_score": score,
        "sell_score": 0.0,
        "reference_price": result.get("ltp"),
        "reference_date": str(datetime.now(IST).date()),
        "data_as_of": datetime.now(IST).isoformat(timespec="seconds"),
    }


def _holding_context(data: Dict[str, Any], symbol: str) -> Dict[str, Any]:
    holdings = data.get("holdings", [])
    holding = next((h for h in holdings if h.get("symbol") == symbol), None)
    if not holding:
        return {}
    qty = float(holding.get("quantity") or 0)
    avg_price = float(holding.get("buyPrice") or 0)
    total_value = sum(
        float(h.get("quantity") or 0) * float(h.get("buyPrice") or 0) for h in holdings)
    weight = (qty * avg_price / total_value * 100) if total_value > 0 else None
    return {
        "holding_qty": qty,
        "holding_avg_price": avg_price or None,
        "holding_weight_pct": round(weight, 2) if weight is not None else None,
    }


def _persist_recommendations(
    results: List[Tuple[str, Dict[str, Any], Dict[str, Any]]],
    trade_date: str,
    scan_id: int,
) -> Dict[str, int]:
    """Append immutable rows. Holdings are re-read AFTER the provider calls so a
    concurrent add/sell during the scan is not clobbered or lost."""
    store = get_store()
    fresh = _load_json(PORTFOLIO_FILE)
    live_symbols = {h.get("symbol") for h in fresh.get("holdings", [])}
    counts = {"scanned": 0, "no_data": 0, "not_enough_data": 0}

    generated_at = datetime.now(IST).isoformat(timespec="seconds")
    from core.recommendation_evaluator import horizon_end_dates
    for symbol, daily, intraday in results:
        if symbol not in live_symbols:
            continue  # holding was removed mid-scan — nothing is recorded
        context = _holding_context(fresh, symbol)
        ends = None
        rec_ids: Dict[str, Optional[str]] = {}
        for horizon, rec in (("daily_swing", daily), ("intraday", intraday)):
            data_as_of = rec.get("data_as_of")
            stale = False
            if data_as_of:
                try:
                    scan_day = datetime.fromisoformat(trade_date).date()
                    data_day = datetime.fromisoformat(str(data_as_of)[:10]).date()
                    stale = data_day < scan_day and is_trading_day(scan_day)
                except (TypeError, ValueError):
                    stale = False
            rec_ids[horizon] = store.insert_recommendation({
                "trade_date": trade_date,
                "symbol": symbol,
                "horizon": horizon,
                "recommendation": rec["recommendation"],
                "generated_at": generated_at,
                "data_as_of": data_as_of,
                "stale_data": stale,
                "reference_price": rec.get("reference_price"),
                "reference_date": rec.get("reference_date"),
                "buy_score": rec.get("buy_score"),
                "sell_score": rec.get("sell_score"),
                "signals": rec.get("signals") or [],
                "strategy": INTRADAY_STRATEGY_NAME if horizon == "intraday" else STRATEGY_NAME,
                "strategy_version": STRATEGY_VERSION,
                "scan_id": scan_id,
                **context,
            })
        label = daily["recommendation"]
        if label == "NO_DATA":
            counts["no_data"] += 1
        elif label == "NOT_ENOUGH_DATA":
            counts["not_enough_data"] += 1
        else:
            counts["scanned"] += 1

        # Evaluation placeholders for the horizons that can complete later.
        if label in ("BUY", "SELL", "HOLD"):
            ends = horizon_end_dates(daily.get("reference_date"))
            daily_ends = {k: ends[k] for k in ("t1", "t5", "t20") if ends.get(k)}
            if rec_ids.get("daily_swing") and daily_ends:
                store.insert_pending_evaluations(rec_ids["daily_swing"], daily_ends)
            # Intraday placeholder: next-session open->close for qualified BUYs.
            if intraday.get("recommendation") == "BUY" and ends and ends.get("intraday_next"):
                if rec_ids.get("intraday"):
                    store.insert_pending_evaluations(
                        rec_ids["intraday"], {"intraday_next": ends["intraday_next"]})
    return counts


def scan_portfolio_recommendations(trigger: str = "scheduled") -> Dict[str, Any]:
    """Scan all current holdings once and persist immutable results."""
    global _last_rescan_monotonic
    now = datetime.now(IST)
    trade_date = now.date().isoformat()

    with _scan_lock:
        store = get_store()
        if store.has_completed_scan(trade_date) and trigger == "scheduled":
            return {"status": "already_scanned", "trade_date": trade_date}

        scan_id = store.insert_scan(
            trade_date=trade_date, trigger=trigger, status="running",
            holdings_count=len(_load_json(PORTFOLIO_FILE).get("holdings", [])))

        try:
            data = _load_json(PORTFOLIO_FILE)
            symbols = [h["symbol"] for h in data.get("holdings", [])]
            if not symbols:
                store.update_scan(scan_id, "completed", "No holdings in portfolio")
                _last_rescan_monotonic = time_module.monotonic()
                return {"status": "completed", "trade_date": trade_date, "count": 0}

            with ThreadPoolExecutor(max_workers=4) as pool:
                daily_results = list(pool.map(_daily_recommendation, symbols))
                intraday_results = list(pool.map(_intraday_recommendation, symbols))

            results = list(zip(symbols, daily_results, intraday_results))
            counts = _persist_recommendations(results, trade_date, scan_id)

            from core.recommendation_evaluator import run_pending_evaluations
            evaluated = run_pending_evaluations(store, trade_date)

            store.update_scan(scan_id, "completed")
            with store.db.transaction() as conn:
                conn.execute(
                    "UPDATE rec_scans SET scanned_count = ?, no_data_count = ?, "
                    "not_enough_data_count = ? WHERE id = ?",
                    (counts["scanned"], counts["no_data"],
                     counts["not_enough_data"], scan_id),
                )
            _last_rescan_monotonic = time_module.monotonic()
            logger.info(
                "Portfolio recommendation scan (%s) for %s: %s scanned, %s no-data, "
                "%s insufficient, %s outcomes evaluated",
                trigger, trade_date, counts["scanned"], counts["no_data"],
                counts["not_enough_data"], evaluated)
            return {
                "status": "completed",
                "trade_date": trade_date,
                "holdings": len(symbols),
                "scanned": counts["scanned"],
                "noData": counts["no_data"],
                "notEnoughData": counts["not_enough_data"],
                "evaluated": evaluated,
            }
        except Exception as exc:
            logger.exception("Portfolio recommendation scan failed")
            store.update_scan(scan_id, "failed", str(exc))
            return {"status": "failed", "trade_date": trade_date, "error": str(exc)}


def run_manual_rescan() -> Dict[str, Any]:
    """Rate-limited (10 min) manual rescan; serialized with the scheduled scan."""
    global _last_rescan_monotonic
    with _scan_lock:
        if _last_rescan_monotonic is not None:
            elapsed = time_module.monotonic() - _last_rescan_monotonic
            if elapsed < MANUAL_RESCAN_COOLDOWN_SEC:
                wait = int(MANUAL_RESCAN_COOLDOWN_SEC - elapsed)
                return {"status": "cooldown",
                        "error": f"Manual rescan available in {wait // 60}m {wait % 60}s"}
    result = scan_portfolio_recommendations(trigger="manual")
    _last_rescan_monotonic = time_module.monotonic()
    return result


def _seconds_until_next_scan(now: datetime) -> float:
    """Delay to the next scan slot at 15:45 IST on a trading day."""
    from core.trader_core import is_trading_day
    days_ahead = 0
    while True:
        target_date = now.date() + timedelta(days=days_ahead)
        candidate = datetime.combine(target_date, SCAN_TIME, tzinfo=IST)
        trading = False
        try:
            trading = is_trading_day(target_date)
        except Exception:
            # Calendar unavailable — fall back to weekday heuristic and surface
            # the limitation via the scan record rather than guessing holidays.
            trading = target_date.weekday() < 5
        if candidate > now and trading:
            return max(1.0, (candidate - now).total_seconds())
        days_ahead += 1


async def daily_portfolio_recommendation_loop() -> None:
    """Run once each NSE trading day after market close, with catch-up after
    restart and an opportunistic pending-evaluation pass between scans."""
    global _last_eval_monotonic
    while True:
        try:
            now = datetime.now(IST)
            store = get_store()
            trade_date = now.date().isoformat()

            # Between scans: evaluate any outcome whose horizon completed.
            if store.all_pending_count() > 0 and \
                    time_module.monotonic() - _last_eval_monotonic >= EVALUATION_RETRY_INTERVAL_SEC:
                from core.recommendation_evaluator import run_pending_evaluations
                try:
                    await asyncio.to_thread(run_pending_evaluations, store, trade_date)
                except Exception:
                    logger.exception("Background evaluation pass failed")
                _last_eval_monotonic = time_module.monotonic()

            due = now.time() >= SCAN_TIME
            already = store.has_completed_scan(trade_date)
            if due and not already:
                try:
                    await asyncio.to_thread(scan_portfolio_recommendations, "scheduled")
                except Exception:
                    logger.exception("Daily portfolio recommendation scan failed")
                await asyncio.sleep(60)
                continue

            await asyncio.sleep(min(_seconds_until_next_scan(now), 300))
        except Exception:
            logger.exception("Recommendation scheduler loop error")
            await asyncio.sleep(60)
