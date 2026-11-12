"""Time Machine API (condensed port of trader-timemachine from Indian Day Trader).

Replays a planned day trade via Monte Carlo simulation (10,000 replays of the
rest of the session) plus chronological walk-forward validation across past
Indian market sessions. Statutory costs and 0.05% slippage deducted. Advisory
only — not a prediction.

Endpoints:
  POST /api/timemachine/run    Run Monte Carlo + walk-forward for a plan
"""

from __future__ import annotations

import asyncio
import datetime
import json
import math
import os
import random
import statistics
import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from core import upstox_data
from core.trader_core import (
    IST,
    calculate_intraday_costs,
    get_default_calendar,
    is_trading_day,
    parse_ist_timestamp,
)
from core.auth import verify_api_key

router = APIRouter(prefix="/api/timemachine", tags=["timemachine"])

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
TM_FILE = os.path.join(DATA_DIR, "timemachine.json")

INTERVAL = 300  # 5-minute bars
SESSION_BARS = 75
OPEN_MIN = 9 * 60 + 15  # 555 (09:15 IST)
CLOSE_MIN = 15 * 60 + 30  # 930 (15:30 IST)
MIN_SESSIONS = 20
SAMPLE_PATHS = 160
BAND_PATHS = 2000
BAND_Q = (0.05, 0.25, 0.5, 0.75, 0.95)
COIN_FLIP = 0.05
STRONG = 0.15
SLIPPAGE_RATE = Decimal("0.0005")


class TMError(Exception):
    pass


class TimeMachineRequest(BaseModel):
    symbol: str = "RELIANCE.NS"
    date: str  # YYYY-MM-DD session date
    entry: float
    stop: float
    target: float
    entry_time: str  # e.g. "09:35 AM" or "09:35"
    side: str = "buy"
    shares: int = 100
    exchange: str = "NSE"
    replays: int = 10000
    seed: int = 19
    window: int = 2
    until: Optional[str] = None  # HH:MM IST (default 15:30)
    split_ratio: float = 0.70
    embargo_sessions: int = 1


def _json_default(o):
    if isinstance(o, (datetime.date, datetime.datetime)):
        return o.isoformat()
    if isinstance(o, float) and (o == float("inf") or o == float("-inf")):
        return None
    raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")


MAX_TM_HISTORY = 20


def _load_tm_history() -> list:
    """Saved Time Machine runs (oldest first). Migrates the old single-doc file."""
    if not os.path.exists(TM_FILE):
        return []
    try:
        with open(TM_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (ValueError, OSError):
        return []
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def _save_tm(doc: dict) -> None:
    """Append a Time Machine run to the history, capped at 20."""
    runs = _load_tm_history()
    runs.append(doc)
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = TM_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(runs[-MAX_TM_HISTORY:], fh, indent=2, default=_json_default)
        fh.write("\n")
    os.replace(tmp, TM_FILE)


def parse_clock(text, what):
    m = __import__("re").match(
        r"^\s*(\d{1,2}):(\d{2})\s*(?:([AaPp])\.?\s*[Mm]\.?)?\s*$", str(text or "")
    )
    if not m:
        raise TMError("%s wants an IST time like 09:35 AM or 15:15, not %r" % (what, text))
    h, mi, ap = int(m.group(1)), int(m.group(2)), (m.group(3) or "").lower()
    if mi > 59 or h > 23 or (ap and not 1 <= h <= 12):
        raise TMError("%s %r is not a clock time" % (what, text))
    if ap == "p" and h != 12:
        h += 12
    elif ap == "a" and h == 12:
        h = 0
    elif not ap and 1 <= h <= 8:
        h += 12
    return h * 60 + mi


def clock12(minutes):
    h, m = divmod(minutes, 60)
    return "%02d:%02d %s" % (h % 12 or 12, m, "AM" if h < 12 else "PM")


def clock24(minutes):
    return "%02d:%02d" % divmod(minutes, 60)


def compute_trade_costs(buy_price, sell_price, qty=100, exchange="NSE", eval_date=None):
    """Indian statutory intraday transaction costs via trader_core.costs."""
    if eval_date is None:
        eval_date = datetime.date.today()
    elif isinstance(eval_date, str):
        try:
            eval_date = datetime.date.fromisoformat(eval_date)
        except ValueError:
            eval_date = datetime.date.today()

    bp = Decimal(str(round(float(buy_price), 2)))
    sp = Decimal(str(round(float(sell_price), 2)))
    q = max(1, int(qty))

    try:
        cb = calculate_intraday_costs(
            buy_price=bp, sell_price=sp, qty=q, exchange=exchange,
            segment="EQ", broker_schedule="discount", effective_date=eval_date,
        )
        return {
            "total_costs": float(cb.total_costs),
            "cost_per_share": float(cb.breakeven_diff),
            "breakdown": cb.to_dict(),
        }
    except Exception:
        turnover = (bp + sp) * q
        brokerage = min(Decimal("40.00"), turnover * Decimal("0.0003"))
        stt = (sp * q * Decimal("0.00025")).quantize(Decimal("1"), rounding=Decimal("ROUND_HALF_UP"))
        exch = turnover * Decimal("0.0000297")
        sebi = turnover * Decimal("0.000001")
        stamp = (bp * q * Decimal("0.00003")).quantize(Decimal("1"), rounding=Decimal("ROUND_HALF_UP"))
        gst = (brokerage + exch + sebi) * Decimal("0.18")
        total = (brokerage + stt + exch + sebi + stamp + gst).quantize(
            Decimal("0.01"), rounding=Decimal("ROUND_HALF_UP"))
        return {"total_costs": float(total), "cost_per_share": float(total / Decimal(q)), "breakdown": {}}


def apply_slippage(price, side, is_entry):
    slip = float(SLIPPAGE_RATE)
    if is_entry:
        return price * (1.0 + slip) if side == "buy" else price * (1.0 - slip)
    return price * (1.0 - slip) if side == "buy" else price * (1.0 + slip)


def evaluate_trade_pnl(entry, exit_price, side, qty=100, exchange="NSE", eval_date=None):
    fill_entry = apply_slippage(entry, side, is_entry=True)
    fill_exit = apply_slippage(exit_price, side, is_entry=False)
    long = side == "buy"
    buy_p = fill_entry if long else fill_exit
    sell_p = fill_exit if long else fill_entry
    cost_info = compute_trade_costs(buy_p, sell_p, qty=qty, exchange=exchange, eval_date=eval_date)
    stat_costs = cost_info["total_costs"]
    raw_pnl = ((exit_price - entry) if long else (entry - exit_price)) * qty
    slip_cost = (abs(fill_entry - entry) + abs(fill_exit - exit_price)) * qty
    gross_pnl = ((fill_exit - fill_entry) if long else (fill_entry - fill_exit)) * qty
    net_pnl = gross_pnl - stat_costs
    return {
        "raw_pnl": round(raw_pnl, 2),
        "fill_entry": round(fill_entry, 2),
        "fill_exit": round(fill_exit, 2),
        "slippage": round(slip_cost, 2),
        "statutory_costs": round(stat_costs, 2),
        "gross_pnl": round(gross_pnl, 2),
        "net_pnl": round(net_pnl, 2),
        "cost_breakdown": cost_info["breakdown"],
    }


def pct(a, q):
    if not a:
        return 0.0
    return a[min(len(a) - 1, max(0, int(q * len(a))))]


def simulate(pool, entry, stop, target, k, last, replays, seed, window, side, shares, exchange, eval_date):
    """Monte Carlo replays of bars k+1..last."""
    long = side == "buy"
    risk = (entry - stop) if long else (stop - entry)
    t_eval = evaluate_trade_pnl(entry, target, side, qty=shares, exchange=exchange, eval_date=eval_date)
    s_eval = evaluate_trade_pnl(entry, stop, side, qty=shares, exchange=exchange, eval_date=eval_date)

    def slot(rng, i):
        return i if window == 0 else min(SESSION_BARS - 1, max(1, i + rng.randint(-window, window)))

    rng = random.Random(seed)
    choice = rng.choice
    outcomes, closes, paths, net_pnls = [], [], [], []

    for n in range(replays):
        p = entry
        outcome = None
        keep = n < SAMPLE_PATHS
        path = [entry]
        for i in range(k + 1, last + 1):
            o, h, l, c = choice(pool[slot(rng, i)])
            hi, lo, cl = p * h, p * l, p * c
            if outcome is None:
                if long:
                    if lo <= stop:
                        outcome = "stop"
                    elif hi >= target:
                        outcome = "target"
                else:
                    if hi >= stop:
                        outcome = "stop"
                    elif lo <= target:
                        outcome = "target"
            p = cl
            if keep:
                path.append(round(p, 2))
        outcomes.append(outcome or "close")
        closes.append(p)
        if keep:
            paths.append(path)
        trade_eval = t_eval if outcome == "target" else (s_eval if outcome == "stop"
            else evaluate_trade_pnl(entry, p, side, qty=shares, exchange=exchange, eval_date=eval_date))
        net_pnls.append(trade_eval["net_pnl"])

    cnt = {x: outcomes.count(x) for x in ("target", "stop", "close")}
    green = sum(1 for o, p in zip(outcomes, closes)
                if o == "target" or (o == "close" and (p > entry if long else p < entry)))
    wins = sum(1 for pnl in net_pnls if pnl > 0)
    srt = sorted(closes)
    srt_pnl = sorted(net_pnls)
    gross_profit = sum(pnl for pnl in net_pnls if pnl > 0)
    gross_loss = sum(abs(pnl) for pnl in net_pnls if pnl < 0)
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)

    cum, peak, max_dd = 0.0, 0.0, 0.0
    for pnl in net_pnls[:1000]:
        cum += pnl
        if cum > peak:
            peak = cum
        dd = peak - cum
        if dd > max_dd:
            max_dd = dd

    rng = random.Random(seed)
    choice = rng.choice
    allp = []
    for n in range(BAND_PATHS):
        p = entry
        path = [entry]
        for i in range(k + 1, last + 1):
            o, h, l, c = choice(pool[slot(rng, i)])
            p = p * c
            path.append(p)
        allp.append(path)
    bands = []
    for j in range(last - k + 1):
        col = sorted(pp[j] for pp in allp)
        bands.append([round(pct(col, q), 2) for q in BAND_Q])

    lo_, hi_ = pct(srt, 0.01), pct(srt, 0.99)
    W = (hi_ - lo_) / 24
    bins = [0] * 24
    for c in srt:
        b = int((c - lo_) / W) if W > 0 else 0
        if 0 <= b < 24:
            bins[b] += 1

    net_Rs = [pnl / (risk * shares) if (risk * shares) > 0 else 0.0 for pnl in net_pnls]

    return {
        "replays": replays,
        "seed": seed,
        "window": window,
        "bars_left": last - k,
        "shares": shares,
        "p_target": round(cnt["target"] / replays, 4),
        "p_stop": round(cnt["stop"] / replays, 4),
        "p_neither": round(cnt["close"] / replays, 4),
        "p_green": round(green / replays, 4),
        "win_rate": round(wins / replays, 4),
        "net_pnl_median": round(pct(srt_pnl, 0.5), 2),
        "net_pnl_p5": round(pct(srt_pnl, 0.05), 2),
        "net_pnl_p95": round(pct(srt_pnl, 0.95), 2),
        "net_pnl_avg": round(statistics.mean(net_pnls), 2),
        "profit_factor": profit_factor,
        "max_drawdown": round(max_dd, 2),
        "median_close": round(pct(srt, 0.5), 2),
        "p5_close": round(pct(srt, 0.05), 2),
        "p95_close": round(pct(srt, 0.95), 2),
        "avg_R": round(statistics.mean(net_Rs), 3),
        "r_at_target": round(((target - entry) if long else (entry - target)) / risk, 4),
        "band_paths": BAND_PATHS,
        "bands": bands,
        "sample_paths": paths,
        "hist": {"lo": round(lo_, 2), "hi": round(hi_, 2), "bins": bins},
    }


def opening_range(D, n):
    rows = [D[i] for i in range(n)]
    return max(b["h"] for b in rows), min(b["l"] for b in rows)


def history_replay(sessions, rule, last, side="buy", shares=100, exchange="NSE"):
    long = side == "buy"
    n = rule["or_minutes"] // 5
    trades = []
    for d, D in sessions:
        oh, ol = opening_range(D, n)
        kk = next((i for i in range(n, last + 1) if (D[i]["c"] > oh if long else D[i]["c"] < ol)), None)
        if kk is None:
            continue
        e = round(D[kk]["c"], 2)
        long_side = side == "buy"
        if long_side:
            s = round((oh + ol) / 2, 2)
        else:
            s = round((oh + ol) / 2, 2)
        risk = (e - s) if long_side else (s - e)
        if risk <= 0:
            continue
        t = round(e + rule["target_r"] * risk, 2) if long_side else round(e - rule["target_r"] * risk, 2)
        oc, exit_p = None, None
        for b in D[kk + 1:last + 1]:
            if (long_side and b["l"] <= s) or ((not long_side) and b["h"] >= s):
                oc, exit_p = "stop", s
                break
            if (long_side and b["h"] >= t) or ((not long_side) and b["l"] <= t):
                oc, exit_p = "target", t
                break
        if oc is None:
            oc, exit_p = "close", D[last]["c"]
        pe = evaluate_trade_pnl(e, exit_p, side, qty=shares, exchange=exchange, eval_date=d)
        trades.append({
            "date": d, "entry": e, "stop": s, "target": t, "exit_price": round(exit_p, 2),
            "outcome": oc, "shares": shares, "net_pnl": pe["net_pnl"],
        })
    net_pnls = [x["net_pnl"] for x in trades]
    gp = sum(x for x in net_pnls if x > 0)
    gl = sum(abs(x) for x in net_pnls if x < 0)
    pf = round(gp / gl, 2) if gl > 0 else (float("inf") if gp > 0 else 0.0)
    cum, peak, mdd = 0.0, 0.0, 0.0
    for pnl in net_pnls:
        cum += pnl
        if cum > peak:
            peak = cum
        dd = peak - cum
        if dd > mdd:
            mdd = dd
    wins = sum(1 for x in net_pnls if x > 0)
    return {
        "sessions": len(sessions),
        "triggered": len(trades),
        "target": sum(1 for x in trades if x["outcome"] == "target"),
        "stop": sum(1 for x in trades if x["outcome"] == "stop"),
        "close": sum(1 for x in trades if x["outcome"] == "close"),
        "win_rate": round(wins / len(trades), 4) if trades else 0.0,
        "net_pnl": round(sum(net_pnls), 2),
        "gross_profit": round(gp, 2),
        "gross_loss": round(gl, 2),
        "profit_factor": pf,
        "max_drawdown": round(mdd, 2),
        "avg_R": round(statistics.mean([x["net_pnl"] / (risk * shares) for x in trades]) if trades else 0, 3),
        "trades": trades,
    }


def walk_forward(sessions, rule, last, side, split_ratio, embargo_sessions, shares, exchange):
    total_s = len(sessions)
    if total_s < 2:
        return None
    split_idx = max(1, min(int(total_s * split_ratio), total_s - 1))
    is_sessions = sessions[:split_idx]
    oos_start = min(total_s, split_idx + embargo_sessions)
    oos_sessions = sessions[oos_start:] or sessions[split_idx:]
    is_res = history_replay(is_sessions, rule, last, side, shares, exchange)
    oos_res = history_replay(oos_sessions, rule, last, side, shares, exchange)

    def pack(res, sess):
        return {
            "sessions": len(sess),
            "from_date": sess[0][0] if sess else None,
            "to_date": sess[-1][0] if sess else None,
            "triggered": res["triggered"],
            "target": res["target"],
            "stop": res["stop"],
            "win_rate": res["win_rate"],
            "net_pnl": res["net_pnl"],
            "profit_factor": res["profit_factor"],
            "max_drawdown": res["max_drawdown"],
            "avg_R": res["avg_R"],
        }

    cf_warning = False
    if is_res["triggered"] > 0 and oos_res["triggered"] > 0:
        if is_res["win_rate"] - oos_res["win_rate"] > 0.15:
            cf_warning = True
        if is_res["profit_factor"] and oos_res["profit_factor"]:
            if is_res["profit_factor"] > 1.2 and oos_res["profit_factor"] < 1.0:
                cf_warning = True

    return {
        "split_ratio": split_ratio,
        "embargo_sessions": embargo_sessions if oos_sessions else 0,
        "in_sample": pack(is_res, is_sessions),
        "out_of_sample": pack(oos_res, oos_sessions),
        "curve_fitting_warning": cf_warning,
    }


@router.post("/run")
def timemachine_run(req: TimeMachineRequest, auth: bool = Depends(verify_api_key)):
    """Run Monte Carlo + walk-forward for a planned trade."""
    try:
        if not 1 <= req.replays <= 1000000:
            raise TMError("replays must be between 1 and 1,000,000")
        if not 0 <= req.window <= 10:
            raise TMError("window must be between 0 and 10 bars")

        sym = req.symbol.upper()
        try:
            plan_date = datetime.date.fromisoformat(req.date)
        except ValueError:
            raise TMError("date wants YYYY-MM-DD, not %r" % req.date)

        cal = get_default_calendar()
        if not cal.is_trading_day(plan_date):
            raise TMError("Market is closed on %s" % req.date)

        entry_min = parse_clock(req.entry_time, "entry_time")
        if (entry_min - OPEN_MIN) % 5:
            raise TMError("entry_time %s is not on the 5-minute grid" % req.entry_time)
        k = (entry_min - OPEN_MIN) // 5 - 1
        if not 0 <= k <= SESSION_BARS - 2:
            raise TMError("entry must close between 9:20 AM and 3:25 PM")

        until_min = CLOSE_MIN
        if req.until:
            until_min = parse_clock(req.until, "--until")
            if (until_min - OPEN_MIN) % 5 or until_min > CLOSE_MIN:
                raise TMError("--until must be on the 5-minute grid and no later than 15:30")
        last = (until_min - OPEN_MIN) // 5 - 1
        if last <= k:
            raise TMError("until %s leaves nothing to replay after entry" % req.until)

        # Fetch historical 5m bars (60 days)
        df = upstox_data.get_stock_data(sym, period="60d", interval="5m")
        if df is None or df.empty:
            raise TMError("no 5-minute data for %s" % sym)

        # Split into sessions
        days_map = {}
        for idx, row in df.iterrows():
            ts = idx
            if hasattr(ts, "strftime"):
                dstr = ts.strftime("%Y-%m-%d")
            else:
                dstr = str(ts)[:10]
            bar_dt = datetime.datetime.strptime(dstr + " " + ts.strftime("%H:%M") if hasattr(ts, "strftime") else str(ts)[:16], "%Y-%m-%d %H:%M").replace(tzinfo=IST)
            if bar_dt.date() not in days_map:
                days_map[bar_dt.date()] = {}
            slot = int((bar_dt - datetime.datetime.combine(bar_dt.date(), datetime.time(9, 15), tzinfo=IST)).total_seconds() // INTERVAL)
            days_map[bar_dt.date()][slot] = {
                "date": dstr, "slot": slot,
                "o": float(row["Open"]), "h": float(row["High"]),
                "l": float(row["Low"]), "c": float(row["Close"]),
                "v": int(row["Volume"]) if "Volume" in row else 0,
            }

        entry_day = days_map.get(plan_date, {})
        if k not in entry_day:
            raise TMError("entry bar not in data for %s" % req.date)

        sessions = []
        for d in sorted(days_map):
            if d >= plan_date:
                continue
            D = days_map[d]
            if len(D) == SESSION_BARS:
                sessions.append((d.isoformat(), [D[i] for i in range(SESSION_BARS)]))

        if len(sessions) < MIN_SESSIONS:
            raise TMError("only %d full sessions before %s; need at least %d" % (len(sessions), req.date, MIN_SESSIONS))

        # Build pool: bar i ratios across sessions
        pool = [[] for _ in range(SESSION_BARS)]
        for _, D in sessions:
            for i in range(1, SESSION_BARS):
                pc = D[i - 1]["c"]
                if pc <= 0:
                    continue
                pool[i].append((D[i]["o"] / pc, D[i]["h"] / pc, D[i]["l"] / pc, D[i]["c"] / pc))

        shares = req.shares
        exchange = req.exchange

        mc = simulate(pool, req.entry, req.stop, req.target, k, last, req.replays,
                      req.seed, req.window, req.side if hasattr(req, 'side') else "buy",
                      shares, exchange, req.date)
        mc = dict(mc, until=clock24(until_min),
                  band_times=[clock24(OPEN_MIN + 5 * (j + 1)) for j in range(k, last + 1)])

        rule = {
            "setup": "orb",
            "or_minutes": 15,
            "stop_rule": "or_mid",
            "target_r": round(((req.target - req.entry) if req.side == "buy" else (req.entry - req.target)) / (req.entry - req.stop), 4),
        }
        history = history_replay(sessions, rule, last, "buy", shares, exchange)
        wf = walk_forward(sessions, rule, last, "buy", req.split_ratio, req.embargo_sessions, shares, exchange)

        doc = {
            "created_by": "trader-timemachine",
            "created_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": "upstox",
            "currency": "INR",
            "disclaimer": "Notice: Intraday trading in equities carries substantial financial risk. Historical simulations do not guarantee future returns.",
            "data": {
                "symbol": sym, "interval": "5m", "range": "60d",
                "pool_sessions": len(sessions),
                "pool_from": sessions[0][0] if sessions else None,
                "pool_to": sessions[-1][0] if sessions else None,
            },
            "plan": {
                "symbol": sym, "date": req.date, "entry": req.entry,
                "stop": req.stop, "target": req.target, "entry_time": req.entry_time,
                "shares": shares, "exchange": exchange,
            },
            "mc": mc,
            "history": history,
            "walk_forward": wf,
            "verdict": (
                "Target first %.1f%% vs stop first %.1f%% (%.1f%% neither). "
                "Net P&L median ₹%+.2f, win rate %.1f%%, profit factor %s."
                % (mc.get("p_target",0)*100, mc.get("p_stop",0)*100, mc.get("p_neither",0)*100,
                   mc.get("net_pnl_median",0), mc.get("win_rate",0)*100,
                   mc.get("profit_factor","N/A"))
            ),
        }
        _save_tm(doc)
        return doc
    except TMError as te:
        raise HTTPException(status_code=400, detail=str(te))


# ---------------------------------------------------------------------------
# Async job wrapper: submit -> poll, so heavy replays never block the event loop
# ---------------------------------------------------------------------------

MAX_TM_JOB_REPLAYS = 20000
MAX_TM_JOBS = 20

_TM_JOBS: dict = {}  # job_id -> {status, created_at, symbol, date, result, error, task}


@router.post("/job")
async def timemachine_job(req: TimeMachineRequest, auth: bool = Depends(verify_api_key)):
    """Submit a Time Machine run as a background job. Poll GET /result/{job_id}."""
    if not 1 <= req.replays <= MAX_TM_JOB_REPLAYS:
        raise HTTPException(
            status_code=400,
            detail="replays must be between 1 and %s for async jobs (use /run for bigger batches)"
            % f"{MAX_TM_JOB_REPLAYS:,}",
        )

    job_id = uuid.uuid4().hex[:12]
    _TM_JOBS[job_id] = {
        "status": "running",
        "created_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "symbol": req.symbol.upper(),
        "date": req.date,
        "result": None,
        "error": None,
    }
    # Keep only the most recent MAX_TM_JOBS jobs
    while len(_TM_JOBS) > MAX_TM_JOBS:
        _TM_JOBS.pop(next(iter(_TM_JOBS)), None)

    async def _worker():
        try:
            doc = await asyncio.to_thread(timemachine_run, req, True)
            _TM_JOBS[job_id]["result"] = doc
            _TM_JOBS[job_id]["status"] = "done"
        except HTTPException as he:
            _TM_JOBS[job_id]["status"] = "error"
            _TM_JOBS[job_id]["error"] = he.detail
        except Exception as ex:  # never leave a job hanging in "running"
            _TM_JOBS[job_id]["status"] = "error"
            _TM_JOBS[job_id]["error"] = "internal error: %s" % ex

    _TM_JOBS[job_id]["task"] = asyncio.create_task(_worker())

    return {"job_id": job_id, "status": "running", "poll": "/api/timemachine/result/%s" % job_id}


@router.get("/result/{job_id}")
def timemachine_result(job_id: str, auth: bool = Depends(verify_api_key)):
    """Poll a Time Machine job. Result is included once status is done."""
    job = _TM_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="unknown job %r (jobs are lost on restart)" % job_id)
    out = {k: job[k] for k in ("status", "created_at", "symbol", "date", "error")}
    if job["status"] == "done":
        out["result"] = job["result"]
    return out


@router.get("/history")
def timemachine_history(full: bool = False, auth: bool = Depends(verify_api_key)):
    """Most recent Time Machine runs (newest first). Heavy payloads only with ?full=true."""
    runs = _load_tm_history()
    runs.reverse()
    if full:
        return {"runs": runs, "count": len(runs)}
    summary = [{k: v for k, v in doc.items() if k not in ("mc", "history", "walk_forward")} for doc in runs]
    return {"runs": summary, "count": len(summary)}
