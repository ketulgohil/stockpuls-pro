"""Daily portfolio recommendation scans using the existing technical signal engine."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from core.portfolio import PORTFOLIO_FILE, _load_json, _save_json
from core.signals import generate_signals
from core.data_fetcher import get_stock_data

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")
SCAN_TIME = time(15, 45)  # after the regular NSE session


def _recommendation_for(symbol: str) -> dict:
    """Summarize existing BUY/SELL technical signals into one portfolio label."""
    try:
        history = get_stock_data(symbol, period="6mo")
        if history is None or history.empty:
            return {"recommendation": "NO_DATA", "signals": [], "buyScore": 0, "sellScore": 0}
        signals = generate_signals(symbol)
    except Exception:
        logger.exception("Portfolio signal scan failed for %s", symbol)
        return {"recommendation": "NO_DATA", "signals": [], "buyScore": 0, "sellScore": 0}

    buy_score = sum(2 if s.get("strength") == "Strong" else 1 for s in signals if s.get("type") == "BUY")
    sell_score = sum(2 if s.get("strength") == "Strong" else 1 for s in signals if s.get("type") == "SELL")
    if buy_score > sell_score:
        decision = "BUY"
    elif sell_score > buy_score:
        decision = "SELL"
    else:
        decision = "HOLD"

    return {
        "recommendation": decision,
        "signals": signals,
        "buyScore": buy_score,
        "sellScore": sell_score,
    }


def scan_portfolio_recommendations() -> dict:
    """Scan all current holdings and persist the results with a completion date."""
    data = _load_json(PORTFOLIO_FILE)
    symbols = [h["symbol"] for h in data.get("holdings", [])]
    scanned_at = datetime.now(IST).isoformat(timespec="seconds")
    if not symbols:
        data["recommendationScan"] = {"scannedAt": scanned_at, "count": 0}
        _save_json(PORTFOLIO_FILE, data)
        return data["recommendationScan"]

    # Keep provider load bounded while keeping this scheduled work off the event loop.
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(_recommendation_for, symbols))

    # Reload after provider calls so a concurrent add/sell is not overwritten.
    data = _load_json(PORTFOLIO_FILE)
    holdings = data.get("holdings", [])
    result_by_symbol = dict(zip(symbols, results))
    scanned_count = 0
    for holding in holdings:
        result = result_by_symbol.get(holding.get("symbol"))
        if result is None:
            continue
        holding["recommendation"] = result["recommendation"]
        holding["recommendationSignals"] = result["signals"]
        holding["recommendationScores"] = {
            "buy": result["buyScore"],
            "sell": result["sellScore"],
        }
        holding["recommendationScannedAt"] = scanned_at
        scanned_count += 1

    data["recommendationScan"] = {"scannedAt": scanned_at, "count": scanned_count}
    _save_json(PORTFOLIO_FILE, data)
    logger.info("Scanned %d portfolio holdings for recommendations", len(holdings))
    return data["recommendationScan"]


def _seconds_until_next_scan(now: datetime) -> float:
    target = datetime.combine(now.date(), SCAN_TIME, tzinfo=IST)
    if now >= target or now.weekday() >= 5:
        days_ahead = 1
        while (now + timedelta(days=days_ahead)).weekday() >= 5:
            days_ahead += 1
        target = datetime.combine((now + timedelta(days=days_ahead)).date(), SCAN_TIME, tzinfo=IST)
    return max(1.0, (target - now).total_seconds())


async def daily_portfolio_recommendation_loop() -> None:
    """Run once each weekday after market close, including catch-up after restart."""
    while True:
        now = datetime.now(IST)
        data = _load_json(PORTFOLIO_FILE)
        last = (data.get("recommendationScan") or {}).get("scannedAt", "")
        try:
            last_date = datetime.fromisoformat(last).astimezone(IST).date() if last else None
        except (TypeError, ValueError):
            last_date = None

        if now.weekday() < 5 and now.time() >= SCAN_TIME and last_date != now.date():
            try:
                await asyncio.to_thread(scan_portfolio_recommendations)
            except Exception:
                logger.exception("Daily portfolio recommendation scan failed")
            await asyncio.sleep(60)
            continue

        await asyncio.sleep(min(_seconds_until_next_scan(now), 300))
