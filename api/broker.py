"""Manual Order Slip API (port of trader-broker from Indian Day Trader).

Formats clean, copy-pasteable order slips for Indian retail brokers
(Zerodha Kite, Groww, Angel One, Upstox Pro). Zero automated broker
execution — all tickets are non-executable proposals requiring manual
entry by the trader.

Endpoints:
  POST /api/broker/slip       Render a manual order slip from a budget proposal
  GET  /api/broker/slips      List all proposed order slips
  POST /api/broker/fill       Record a manual fill (reconciliation)
"""

from __future__ import annotations

import datetime
import json
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from core.auth import verify_api_key

router = APIRouter(prefix="/api/broker", tags=["broker"])

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
SLIPS_FILE = os.path.join(DATA_DIR, "broker_slips.json")
FILL_LOG = os.path.join(DATA_DIR, "fill_log.json")
AUDIT_LOG = os.path.join(DATA_DIR, "audit.log")

BROKERS = ("zerodha", "groww", "angelone", "upstox", "plain")


class SlipRequest(BaseModel):
    symbol: str
    quantity: int
    price: float
    stop: Optional[float] = None
    target: Optional[float] = None
    exchange: str = "NSE"
    product: str = "MIS"
    order_type: str = "LIMIT"
    broker: str = "zerodha"
    setup: Optional[str] = None
    note: Optional[str] = None


class FillRequest(BaseModel):
    ticket_id: str
    price: float
    quantity: int
    reason: Optional[str] = None


class SlipResponse(BaseModel):
    ticket_id: str
    symbol: str
    broker: str
    slip: str
    status: str


def _save_json(path, doc):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (ValueError, OSError):
        return default


def _audit(event: str, detail: str):
    os.makedirs(DATA_DIR, exist_ok=True)
    line = "%s | %s | %s\n" % (
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), event, detail)
    with open(AUDIT_LOG, "a", encoding="utf-8") as fh:
        fh.write(line)


def render_slip(sym, qty, price, stop, target, exchange, product, order_type, broker, setup, note):
    """Render a copy-pasteable order slip for the chosen broker."""
    date_str = datetime.date.today().isoformat().replace("-", "")
    ticket_id = "%s-%s" % (date_str, sym.upper())
    sym_clean = sym.upper().replace(".NS", "").replace(".BO", "")
    price_str = "%.2f" % price
    stop_str = "%.2f" % stop if stop else "-"
    target_str = "%.2f" % target if target else "-"
    setup_word = setup or "day trade"
    why = ("%s on %s: %d shares @ %s, SL %s, TGT %s" % (
        setup_word, sym_clean, qty, price_str, stop_str, target_str))

    if broker.lower() == "zerodha":
        slip = (
            "BUY %s QTY %d LIMIT %s MIS\n"
            "SL: %s | TGT: %s\n"
            "Note: %s" % (sym_clean, qty, price_str, stop_str, target_str, why)
        )
    elif broker.lower() == "groww":
        slip = (
            "Groww Order:\n"
            "Symbol: %s\n"
            "Exchange: %s\n"
            "Product: %s\n"
            "Order Type: %s\n"
            "Quantity: %d\n"
            "Price: %s\n"
            "Stop Loss: %s\n"
            "Target: %s\n"
            "%s" % (sym_clean, exchange, product, order_type, qty, price_str,
                    stop_str, target_str, why)
        )
    elif broker.lower() == "angelone":
        slip = (
            "Angel One:\n"
            "BUY %s | Qty: %d | Price: %s | Product: %s\n"
            "SL Trigger: %s | Target: %s\n"
            "%s" % (sym_clean, qty, price_str, product, stop_str, target_str, why)
        )
    elif broker.lower() == "upstox":
        slip = (
            "Upstox Pro:\n"
            "BUY %s [%s:%s] %s %d @ %s\n"
            "SL: %s | TGT: %s\n"
            "%s" % (sym_clean, exchange, product, order_type, qty, price_str,
                    stop_str, target_str, why)
        )
    else:
        slip = (
            "PLAIN ORDER SLIP:\n"
            "BUY %s QTY %d @ %s (%s, %s, %s)\n"
            "SL: %s | TGT: %s\n"
            "%s" % (sym_clean, qty, price_str, exchange, product, order_type,
                    stop_str, target_str, why)
        )

    return {
        "ticket_id": ticket_id,
        "symbol": sym_clean,
        "exchange": exchange,
        "product": product,
        "order_type": order_type,
        "side": "BUY",
        "quantity": qty,
        "price": price_str,
        "stop": stop_str,
        "target": target_str,
        "broker": broker.lower(),
        "setup": setup_word,
        "note": note or "Manual copy-paste slip. No automated execution.",
        "why": why,
        "slip": slip,
        "status": "PROPOSED",
        "is_proposal": True,
        "created": datetime.datetime.now().isoformat(),
    }


@router.post("/slip", response_model=SlipResponse)
def render_order_slip(req: SlipRequest, auth: bool = Depends(verify_api_key)):
    """Render a manual order slip for a broker terminal."""
    try:
        if req.broker.lower() not in BROKERS:
            raise HTTPException(status_code=400, detail="broker must be one of: %s" % ", ".join(BROKERS))
        slip = render_slip(
            req.symbol, req.quantity, req.price, req.stop, req.target,
            req.exchange, req.product, req.order_type, req.broker,
            req.setup, req.note,
        )
        slips = _load_json(SLIPS_FILE, {"slips": []})
        slips["slips"].append(slip)
        _save_json(SLIPS_FILE, slips)
        _audit("SLIP_RENDERED", "%s %s %d shares @ %s (%s)" % (
            req.broker, req.symbol, req.quantity, req.price, slip["ticket_id"]))
        return {
            "ticket_id": slip["ticket_id"],
            "symbol": slip["symbol"],
            "broker": slip["broker"],
            "slip": slip["slip"],
            "status": slip["status"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/slips")
def list_slips(auth: bool = Depends(verify_api_key)):
    """List all proposed order slips."""
    return _load_json(SLIPS_FILE, {"slips": []})


@router.post("/fill")
def record_fill(req: FillRequest, auth: bool = Depends(verify_api_key)):
    """Record a manual fill (reconciliation) for a ticket."""
    try:
        fill = {
            "ticket_id": req.ticket_id,
            "price": req.price,
            "quantity": req.quantity,
            "reason": req.reason or "manual fill",
            "recorded_at": datetime.datetime.now().isoformat(),
        }
        log = _load_json(FILL_LOG, {"fills": []})
        log["fills"].append(fill)
        _save_json(FILL_LOG, log)
        _audit("FILL_RECORDED", "%s @ %s x%d (%s)" % (
            req.ticket_id, req.price, req.quantity, fill["reason"]))
        return {"ticket_id": req.ticket_id, "message": "fill recorded", "fill": fill}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
