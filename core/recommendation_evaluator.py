"""Outcome evaluation for stored portfolio recommendations.

Definitions (documented in the UI as-is):

* BUY  (daily_swing)  — "worked" when the net forward close-to-close return over
  the horizon is > 0 after subtracting the estimated round-trip cost (0.30%).
* SELL (daily_swing)  — "worked" when the net return of *exiting* is > 0, i.e.
  minus the forward return minus cost (price fell more than costs).
* HOLD (daily_swing)  — "worked" when the forward close stayed within the
  +/-2.0% neutral band (neither a missed large up-move nor a large drawdown).
* BUY  (intraday)     — "worked" when the next trading session's open-to-close
  net return is > 0 after costs (score >= 80 qualified confluence).

Every outcome is gross-return-recorded too, so both views exist. Horizons for
daily records are the next 1, 5 and 20 NSE trading sessions after the last
candle actually used (never a calendar day — weekends/holidays are skipped).
A single-day move beyond 20% inside the window flags a suspected split/bonus/
corporate action and the row is excluded from headline statistics instead of
silently distorting them. Horizons that have not completed stay PENDING.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from core.trader_core import IST, get_default_calendar, is_trading_day

logger = logging.getLogger(__name__)

ESTIMATED_COST_PCT = 0.30      # round-trip delivery cost incl. STT + slippage estimate
HOLD_NEUTRAL_BAND_PCT = 2.0    # |fwd return| within this band => HOLD worked
CORP_ACTION_MOVE_PCT = 20.0    # single-day close move above this => suspect split/bonus
DATA_GRACE_DAYS = 10           # calendar days after horizon end before giving up
BENCHMARK_SYMBOL = "^NSEI"     # NIFTY 50 — same source the portfolio benchmark uses

DAILY_HORIZONS = ("t1", "t5", "t20")
INTRADAY_HORIZONS = ("intraday_next",)

SUCCESS_DEFINITIONS = {
    "daily_swing": {
        "BUY": "Next-1/5/20-session close-to-close return > 0 after estimated "
               "round-trip cost (0.30%).",
        "SELL": "Exit return (negative of forward return) > 0 after cost.",
        "HOLD": "Forward close stayed within the +/-2.0% neutral band over the "
                "same horizons.",
    },
    "intraday": {
        "BUY": "Next trading session open-to-close return > 0 after estimated "
               "round-trip cost (0.30%). Qualified confluence score >= 80 only.",
        "NONE": "No intraday signal fired; nothing is evaluated.",
    },
}


def _as_date(value: Any):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return datetime.fromisoformat(str(value)[:10]).date()


def next_trading_dates(after: Any, count: int) -> List[Any]:
    """The next `count` NSE trading dates strictly after `after` (IST calendar)."""
    cal = get_default_calendar()
    d = _as_date(after)
    out = []
    while len(out) < count:
        d = d + timedelta(days=1)
        try:
            if is_trading_day(d, calendar=cal):
                out.append(d)
        except Exception:
            # Fail-closed: treat unknown calendar errors as non-trading and move on.
            continue
    return out


def horizon_end_dates(reference_date: Any) -> Dict[str, str]:
    """Map horizon_key -> ISO end date, computed from the last candle used."""
    ref = _as_date(reference_date)
    ends: Dict[str, str] = {}
    if ref is None:
        return ends
    daily = next_trading_dates(ref, 20)
    if len(daily) >= 1:
        ends["t1"] = daily[0].isoformat()
    if len(daily) >= 5:
        ends["t5"] = daily[4].isoformat()
    if len(daily) >= 20:
        ends["t20"] = daily[19].isoformat()
    ends["intraday_next"] = daily[0].isoformat() if daily else None
    return ends


def _candles_by_date(symbol: str) -> Dict[str, Dict[str, float]]:
    from core.data_fetcher import get_stock_data
    df = get_stock_data(symbol, period="6mo", interval="1d")
    if df is None or df.empty:
        return {}
    out: Dict[str, Dict[str, float]] = {}
    for idx, row in df.iterrows():
        try:
            date_str = str(idx)[:10]
        except Exception:
            continue
        try:
            out[date_str] = {
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
            }
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _pct_change(a: float, b: float) -> float:
    if not a:
        return 0.0
    return (b - a) / a * 100.0


def evaluate_row(row: Dict[str, Any], candles: Dict[str, Dict[str, float]],
                 bench: Dict[str, Dict[str, float]], today: str) -> Dict[str, Any]:
    """Compute one evaluation row. Returns fields for update_evaluation."""
    rec_type = row.get("recommendation")
    horizon_key = row.get("horizon_key")
    ref_date = _as_date(row.get("reference_date")) or _as_date(row.get("trade_date"))
    end_date = _as_date(row.get("end_date"))
    ref_price = row.get("reference_price")

    base: Dict[str, Any] = {"evaluated_at": datetime.now(IST).isoformat(timespec="seconds")}
    if ref_date is None or end_date is None or ref_price is None:
        base.update(status="DATA_UNAVAILABLE", note="Missing reference price/date")
        return base

    window = sorted(d for d in candles if ref_date.isoformat() < d <= end_date.isoformat())
    if end_date.isoformat() not in candles:
        last_available = max(candles, key=str) if candles else None
        grace = (datetime.now(IST).date() - end_date).days
        if last_available and last_available > end_date.isoformat():
            # Provider eventually gave a candle past the window; but the exact
            # end-date candle is missing -> still not evaluable precisely.
            base.update(status="DATA_UNAVAILABLE",
                        note="No candle for horizon end date")
            return base
        if grace > DATA_GRACE_DAYS:
            base.update(status="DATA_UNAVAILABLE",
                        note="Horizon end never produced a candle (suspended/delisted?)")
            return base
        return {"status": "PENDING"}  # provider lag — keep waiting

    end_price = candles[end_date.isoformat()]["close"]
    days_used = len(window)

    gross = _pct_change(float(ref_price), end_price)
    mfe = mae = 0.0
    for d in window:
        c = candles[d]
        mfe = max(mfe, _pct_change(float(ref_price), c["high"]))
        mae = min(mae, _pct_change(float(ref_price), c["low"]))

    # Suspected corporate action: any day-over-day close move inside the window
    # beyond the threshold (ref -> first day counts too).
    prev_close = float(ref_price)
    suspect = False
    for d in window:
        close = candles[d]["close"]
        if prev_close and abs(_pct_change(prev_close, close)) > CORP_ACTION_MOVE_PCT:
            suspect = True
        prev_close = close

    notes: List[str] = []
    if days_used == 0:
        notes.append("No candles between reference and horizon end (provider gap)")

    bench_return = None
    bench_window = sorted(d for d in bench if ref_date.isoformat() < d <= end_date.isoformat())
    if end_date.isoformat() in bench and end_date.isoformat() != ref_date.isoformat():
        bench_ref_date = max((d for d in bench if d <= ref_date.isoformat()), default=None)
        if bench_ref_date:
            bench_return = _pct_change(
                bench[bench_ref_date]["close"], bench[end_date.isoformat()]["close"])

    fields: Dict[str, Any] = {
        "end_date": end_date.isoformat(),
        "ref_price": float(ref_price),
        "end_price": end_price,
        "gross_return_pct": round(gross, 4),
        "cost_pct": ESTIMATED_COST_PCT,
        "mfe_pct": round(mfe, 4),
        "mae_pct": round(mae, 4),
        "days_used": days_used,
        "evaluated_at": base["evaluated_at"],
    }
    if bench_return is not None:
        fields["bench_return_pct"] = round(bench_return, 4)

    if suspect:
        fields["status"] = "SUSPECTED_CORP_ACTION"
        fields["note"] = ("Single-day move > 20% inside window — suspected split/"
                          "bonus/corporate action; excluded from statistics")
        return fields

    if horizon_key == "intraday_next":
        entry = candles[end_date.isoformat()]["open"]
        session_return = _pct_change(entry, end_price) if entry else 0.0
        net = session_return - ESTIMATED_COST_PCT
        fields["gross_return_pct"] = round(session_return, 4)
        fields["net_return_pct"] = round(net, 4)
        if rec_type == "BUY":
            fields["status"] = "WORKED" if net > 0 else "NOT_WORKED"
        else:
            fields["status"] = "NEUTRAL"  # NONE/no-signal intraday rows
            fields["note"] = "No qualified intraday signal; nothing evaluated"
        return fields

    if rec_type == "BUY":
        net = gross - ESTIMATED_COST_PCT
        fields["net_return_pct"] = round(net, 4)
        fields["status"] = "WORKED" if net > 0 else "NOT_WORKED"
    elif rec_type == "SELL":
        net = -gross - ESTIMATED_COST_PCT
        fields["net_return_pct"] = round(net, 4)
        fields["status"] = "WORKED" if net > 0 else "NOT_WORKED"
    elif rec_type == "HOLD":
        fields["net_return_pct"] = round(gross, 4)  # no trade => no cost
        within = abs(gross) <= HOLD_NEUTRAL_BAND_PCT
        fields["status"] = "WORKED" if within else "NOT_WORKED"
        fields["note"] = (
            "Within +/-2% neutral band" if within
            else f"Moved {gross:+.2f}% — outside +/-2% neutral band"
        )
    else:
        # NO_DATA / NOT_ENOUGH_DATA records: nothing to evaluate.
        fields["status"] = "NEUTRAL"
        fields["note"] = "No tradeable recommendation; not evaluated"
        return fields

    if bench_return is not None:
        fields["excess_return_pct"] = round(
            (fields.get("net_return_pct") or 0.0) - bench_return, 4)
    if notes and not fields.get("note"):
        fields["note"] = "; ".join(notes)
    return fields


def run_pending_evaluations(store, today: str, limit: int = 200) -> int:
    """Evaluate every PENDING outcome whose horizon end date has arrived."""
    rows = store.due_pending_evaluations(today)
    if not rows:
        return 0
    symbols = sorted({r["symbol"] for r in rows})
    candles_by_symbol = {s: _candles_by_date(s) for s in symbols}
    bench = _candles_by_date(BENCHMARK_SYMBOL)

    evaluated = 0
    for row in rows[:limit]:
        symbol = row["symbol"]
        try:
            fields = evaluate_row(
                row, candles_by_symbol.get(symbol) or {}, bench, today)
        except Exception:
            logger.exception("Evaluation failed for %s (%s)", symbol, row.get("horizon_key"))
            continue
        if fields.get("status") == "PENDING":
            continue  # provider still catching up
        store.update_evaluation(row["recommendation_id"], row["horizon_key"], fields)
        evaluated += 1
    return evaluated


def summarize_performance(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate evaluation rows into dashboard statistics.

    Suspected corporate-action rows and NEUTRAL (non-tradeable) rows are
    excluded from success rates but reported separately. Every rate carries
    its denominator (e.g. "3/7").
    """
    def _f(v):
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    groups: Dict[str, List[Dict[str, Any]]] = {}
    counters = {"pending": 0, "failed": 0, "suspected_corp_action": 0, "neutral": 0,
                "total": len(rows)}
    for row in rows:
        status = (row.get("eval_status") or "PENDING").upper()
        if status == "PENDING":
            counters["pending"] += 1
        elif status in ("DATA_UNAVAILABLE",):
            counters["failed"] += 1
        elif status == "SUSPECTED_CORP_ACTION":
            counters["suspected_corp_action"] += 1
        elif status == "NEUTRAL":
            counters["neutral"] += 1
        if status in ("WORKED", "NOT_WORKED"):
            key = f"{row.get('recommendation')}|{row.get('horizon_key')}"
            groups.setdefault(key, []).append(row)

    buckets = []
    for key, items in sorted(groups.items()):
        rec_type, hkey = key.split("|", 1)
        nets = [_f(i.get("net_return_pct")) for i in items]
        nets = [n for n in nets if n is not None]
        excess = [_f(i.get("excess_return_pct")) for i in items]
        excess = [e for e in excess if e is not None]
        worked = sum(1 for i in items if (i.get("eval_status") or "").upper() == "WORKED")
        total = len(items)
        sorted_nets = sorted(nets)
        mid = len(sorted_nets) // 2
        median = (sorted_nets[mid] if len(sorted_nets) % 2
                  else (sorted_nets[mid - 1] + sorted_nets[mid]) / 2) if sorted_nets else None
        buckets.append({
            "recommendation": rec_type,
            "horizonKey": hkey,
            "worked": worked,
            "total": total,
            "successRate": round(worked / total * 100, 1) if total else None,
            "successRatio": f"{worked}/{total}",
            "avgNetReturnPct": round(sum(nets) / len(nets), 3) if nets else None,
            "medianNetReturnPct": round(median, 3) if median is not None else None,
            "avgExcessVsNiftyPct": round(sum(excess) / len(excess), 3) if excess else None,
        })

    return {
        "buckets": buckets,
        "counts": counters,
        "definitions": SUCCESS_DEFINITIONS,
        "costModel": {
            "estimatedRoundTripCostPct": ESTIMATED_COST_PCT,
            "holdNeutralBandPct": HOLD_NEUTRAL_BAND_PCT,
            "benchmark": "NIFTY 50 (^NSEI), close-to-close over the same window",
        },
    }
