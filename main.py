from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import json
import asyncio
import time
from datetime import datetime
from api import (
    stocks, screener, signals, portfolio, sector, tools,
    news, backtest, market, compare, patterns,
    correlation, breadth, fundamentals, analysis, alerts, export, ai, gemini, advanced, more, features,
    mutual_funds, block_deals, quarterly_results, screener_strategies, downstox, sentinel, upstox_trading,
    exit, budget, risk, scanner, entry, timemachine, analyst, alerts, broker, institutional, news, dashboard, auth
)
from core.auth import verify_api_key
import inngest.fast_api
from core.workflows.inngest_client import inngest_client
from core.workflows.functions import inngest_functions
from core.sentinel.dispatcher import dispatcher
from core.sentinel.engine import sentinel_engine
from core.upstox.stream import upstox_engine
from core import upstox_data
from core.data_fetcher import ALL_SYMBOLS, get_stock_data, get_live_price
from core.upstox_data import ensure_instruments
from core.trader_core import IST
from core.portfolio_recommendations import daily_portfolio_recommendation_loop

app = FastAPI(
    title="Indian Stock Market Analysis Platform",
    description="Technical analysis, screening, and signals for NSE/BSE stocks",
    version="5.0.0"
)

@app.on_event("startup")
async def startup_event():
    print("🚀 StockPulse Pro started successfully!")
    sentinel_engine.start()
    app.state.portfolio_recommendation_task = asyncio.create_task(daily_portfolio_recommendation_loop())
    if upstox_engine.client.is_authenticated:
        upstox_engine.start()
        print(f"📡 Upstox live engine started ({len(upstox_engine.symbols)} symbols)")
    else:
        print("⚠️  Upstox live engine not started: UPSTOX_ACCESS_TOKEN is not configured.")

@app.on_event("shutdown")
async def shutdown_event():
    sentinel_engine.stop()
    upstox_engine.stop()
    task = getattr(app.state, "portfolio_recommendation_task", None)
    if task:
        task.cancel()

app.include_router(stocks.router)
app.include_router(screener.router)
app.include_router(signals.router)
app.include_router(portfolio.router)
app.include_router(sector.router)
app.include_router(tools.router)
app.include_router(news.router)
app.include_router(backtest.router)
app.include_router(market.router)
app.include_router(compare.router)
app.include_router(patterns.router)
app.include_router(correlation.router)
app.include_router(breadth.router)
app.include_router(fundamentals.router)
app.include_router(analysis.router)
app.include_router(alerts.router)
app.include_router(export.router)
app.include_router(ai.router)
app.include_router(gemini.router)
app.include_router(advanced.router)
app.include_router(exit.router)
app.include_router(budget.router)
app.include_router(risk.router)
app.include_router(scanner.router)
app.include_router(entry.router)
app.include_router(timemachine.router)
app.include_router(analyst.router)
app.include_router(dashboard.router)
app.include_router(broker.router)
app.include_router(institutional.router)
app.include_router(more.router)
app.include_router(features.router)
app.include_router(mutual_funds.router)
app.include_router(block_deals.router)
app.include_router(quarterly_results.router)
app.include_router(screener_strategies.router)
app.include_router(downstox.router)
app.include_router(sentinel.router)
app.include_router(upstox_trading.router)
app.include_router(upstox_trading.ws_router)
app.include_router(auth.router)

app.mount("/static", StaticFiles(directory="static"), name="static")

inngest.fast_api.serve(app, inngest_client, inngest_functions)


# ===== WebSocket Live Price Streaming =====

MAX_CONNECTIONS = 50
MAX_SYMBOLS_PER_CLIENT = 200

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> bool:
        if len(self.active_connections) >= MAX_CONNECTIONS:
            await websocket.close(code=1008, reason="Server busy: connection limit reached")
            return False
        await websocket.accept()
        self.active_connections.append(websocket)
        return True

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)


ws_manager = ConnectionManager()


LIVE_PRICE_POLL_SECONDS = 3
DEFAULT_LIVE_SYMBOLS = ["^NSEI", "^NSEBANK", "^BSESN"]

# In-memory quote cache to avoid Upstox rate limits (UDAPI10005)
_live_price_cache = {}
_live_price_cache_ttl = 5  # seconds


async def _fetch_live_prices(symbols):
    """Fetch legacy-shaped quotes off the event loop, with caching."""
    now = time.time()
    symbols = list(symbols)
    
    # Check cache first
    to_fetch = []
    cached_results = {}
    for sym in symbols:
        entry = _live_price_cache.get(sym)
        if entry and (now - entry["ts"]) < _live_price_cache_ttl:
            cached_results[sym] = entry["data"]
        else:
            to_fetch.append(sym)
    
    if to_fetch:
        prices_raw = await asyncio.to_thread(upstox_data.get_quotes, to_fetch)
        for sym, q in prices_raw.items():
            _live_price_cache[sym] = {"ts": now, "data": q}
            cached_results[sym] = q
    
    return {
        sym: {
            "price": q["price"],
            "change": q["change"],
            "changePercent": q["changePercent"],
        }
        for sym, q in cached_results.items()
    }


@app.websocket("/ws/live-prices")
async def websocket_live_prices(websocket: WebSocket):
    if not await ws_manager.connect(websocket):
        return
    symbols = list(DEFAULT_LIVE_SYMBOLS)

    async def push_prices():
        try:
            prices = await _fetch_live_prices(symbols)
        except Exception:
            prices = {}
        await websocket.send_text(json.dumps({
            "prices": prices,
            "timestamp": str(datetime.now())
        }))

    try:
        # Wait briefly for the client's initial subscription, but don't block
        # the first update if it doesn't send one.
        try:
            data = await asyncio.wait_for(websocket.receive_text(), timeout=2.0)
            params = json.loads(data)
            incoming = params.get("symbols") or []
            if incoming and isinstance(incoming, list):
                symbols = [str(s).strip().upper() for s in incoming[:MAX_SYMBOLS_PER_CLIENT] if s]
        except asyncio.TimeoutError:
            pass

        await push_prices()

        while True:
            # Listen for subscription changes while waiting for the next tick.
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(), timeout=LIVE_PRICE_POLL_SECONDS
                )
            except asyncio.TimeoutError:
                await push_prices()
                continue

            try:
                params = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                continue

            incoming = params.get("symbols") or []
            if incoming and isinstance(incoming, list):
                symbols = [str(s).strip().upper() for s in incoming[:MAX_SYMBOLS_PER_CLIENT] if s]
                await push_prices()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


# ===== WebSocket Sentinel Real-time Alerts & Digests =====

@app.websocket("/ws/sentinel")
async def websocket_sentinel(websocket: WebSocket):
    await websocket.accept()
    dispatcher.register_ws(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        dispatcher.unregister_ws(websocket)
    except Exception:
        dispatcher.unregister_ws(websocket)


@app.get("/api/options/chain")
async def get_option_chain(expiry: str = None):
    """Get option chain data for NIFTY/BANKNIFTY"""
    try:
        return upstox_data.get_option_chain("^NSEI", expiry=expiry)
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/market/depth/{symbol}")
async def get_market_depth(symbol: str):
    """Get real market depth from the Upstox order book"""
    from core.upstox_data import get_client, run_async
    try:
        client = get_client()
        depth = run_async(client.get_market_depth(symbol)) or {}
        if depth.get("error"):
            return {"symbol": symbol, "error": depth["error"]}

        bids = depth.get("bids") or depth.get("buy") or []
        asks = depth.get("asks") or depth.get("sell") or []
        current_price = float(depth.get("currentPrice") or 0.0)
        total_bid_qty = depth.get("totalBidQty")
        if total_bid_qty is None:
            total_bid_qty = sum(b.get("quantity", 0) for b in bids)
        total_ask_qty = depth.get("totalAskQty")
        if total_ask_qty is None:
            total_ask_qty = sum(a.get("quantity", 0) for a in asks)

        best_bid = bids[0].get("price", 0) if bids else 0
        best_ask = asks[0].get("price", 0) if asks else 0
        spread = depth.get("spread")
        if spread is None:
            spread = round(best_ask - best_bid, 2) if best_bid and best_ask else 0

        return {
            "symbol": symbol,
            "currentPrice": round(current_price, 2),
            "bids": bids,
            "asks": asks,
            "totalBidQty": total_bid_qty,
            "totalAskQty": total_ask_qty,
            "bidAskRatio": depth.get("bidAskRatio", round(total_bid_qty / total_ask_qty, 2) if total_ask_qty > 0 else 0),
            "spread": round(spread, 2),
            "spreadPercent": depth.get("spreadPercent", round((spread / current_price) * 100, 3) if current_price > 0 else 0),
            "timestamp": depth.get("timestamp") or datetime.now().isoformat()
        }
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}


@app.get("/")
def root():
    # The app shell is not content-hashed, so never let the browser reuse a
    # stale copy (this used to hide live-price updates behind cached HTML).
    return FileResponse(
        "static/index.html",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/api/market/status")
async def get_market_status():
    """Get current market status for NSE/BSE"""
    now = datetime.now(IST)
    hour = now.hour
    minute = now.minute
    weekday = now.weekday()  # 0=Mon, 6=Sun

    if weekday >= 5:
        status = "CLOSED"
        message = "Market closed (Weekend)"
    elif hour < 9 or (hour == 9 and minute < 15):
        status = "PRE_OPEN"
        message = f"Pre-open session. Market opens at 9:15 AM"
    elif hour == 9 and minute >= 15 and minute < 30:
        status = "OPENING"
        message = "Market is opening"
    elif (hour == 9 and minute >= 30) or (hour >= 10 and hour < 15) or (hour == 15 and minute <= 30):
        status = "OPEN"
        message = "Market is open"
    elif hour == 15 and minute > 30:
        status = "CLOSING"
        message = "Closing session"
    else:
        status = "CLOSED"
        message = "Market closed"

    return {
        "status": status,
        "message": message,
        "timestamp": now.isoformat(),
        "isMarketHours": status in ["OPEN", "OPENING", "CLOSING"]
    }


@app.get("/api/market/pulse")
async def get_market_pulse():
    """Calculate overall market pulse/sentiment"""
    pulse_data = {
        "score": 0,  # -100 to +100
        "label": "Neutral",
        "indicators": []
    }

    try:
        quotes = upstox_data.get_quotes(["^NSEI", "^NSEBANK", "^BSESN", "^INDIAVIX"])

        # Check NIFTY trend
        nifty = quotes.get("^NSEI")
        if nifty:
            nifty_change = nifty.get("changePercent", 0)
            pulse_data["indicators"].append({
                "name": "NIFTY 50",
                "value": round(nifty.get("price", 0), 2),
                "change": round(nifty_change, 2),
                "signal": "bullish" if nifty_change > 0.2 else ("bearish" if nifty_change < -0.2 else "neutral")
            })
            pulse_data["score"] += nifty_change * 10

        # Check BANKNIFTY trend
        banknifty = quotes.get("^NSEBANK")
        if banknifty:
            bank_change = banknifty.get("changePercent", 0)
            pulse_data["indicators"].append({
                "name": "BANK NIFTY",
                "value": round(banknifty.get("price", 0), 2),
                "change": round(bank_change, 2),
                "signal": "bullish" if bank_change > 0.3 else ("bearish" if bank_change < -0.3 else "neutral")
            })
            pulse_data["score"] += bank_change * 8

        # Check SENSEX trend
        sensex = quotes.get("^BSESN")
        if sensex:
            sensex_change = sensex.get("changePercent", 0)
            pulse_data["indicators"].append({
                "name": "SENSEX",
                "value": round(sensex.get("price", 0), 2),
                "change": round(sensex_change, 2),
                "signal": "bullish" if sensex_change > 0.2 else ("bearish" if sensex_change < -0.2 else "neutral")
            })
            pulse_data["score"] += sensex_change * 7

        # Check VIX (fear index)
        vix = quotes.get("^INDIAVIX")
        if vix and vix.get("price"):
            vix_value = vix.get("price", 0)
            pulse_data["indicators"].append({
                "name": "INDIA VIX",
                "value": round(vix_value, 2),
                "change": round(vix.get("changePercent", 0), 2),
                "signal": "bearish" if vix_value > 20 else ("bullish" if vix_value < 12 else "neutral")
            })
            # High VIX = fear = bearish
            if vix_value > 20:
                pulse_data["score"] -= 20
            elif vix_value < 12:
                pulse_data["score"] += 10

        # Cap score between -100 and 100
        pulse_data["score"] = max(-100, min(100, pulse_data["score"]))

        # Determine label
        if pulse_data["score"] > 30:
            pulse_data["label"] = "Strong Bullish"
            pulse_data["color"] = "#00ff88"
        elif pulse_data["score"] > 10:
            pulse_data["label"] = "Bullish"
            pulse_data["color"] = "#00cc6a"
        elif pulse_data["score"] > -10:
            pulse_data["label"] = "Neutral"
            pulse_data["color"] = "#ffaa00"
        elif pulse_data["score"] > -30:
            pulse_data["label"] = "Bearish"
            pulse_data["color"] = "#ff6b35"
        else:
            pulse_data["label"] = "Strong Bearish"
            pulse_data["color"] = "#ff3838"

    except Exception as e:
        pulse_data["error"] = str(e)

    return pulse_data


@app.get("/health")
def health():
    return {"status": "ok", "version": "5.0.0"}


@app.get("/api/market/volume-alerts")
async def get_volume_alerts():
    """Get stocks with unusual volume activity"""
    try:
        # Use ALL available NSE instruments from the Upstox instrument database
        instruments = ensure_instruments()
        if not instruments:
            return {"alerts": [], "timestamp": datetime.now().isoformat()}

        # Filter to NSE equity symbols (those ending with .NS or without exchange suffix)
        symbols = []
        for k, v in instruments.items():
            # Include symbols that look like NSE equities
            clean = k.upper().replace(".NS", "").replace(".BO", "").strip()
            if clean and clean not in symbols:
                symbols.append(clean)

        # Process in batches of 500 (Upstox API limit)
        all_alerts = []
        batch_size = 500
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i+batch_size]
            quotes = await asyncio.to_thread(get_quotes, batch)

            for symbol in batch:
                try:
                    quote = quotes.get(symbol) or quotes.get(symbol.upper())
                    if not quote:
                        continue

                    hist = await asyncio.to_thread(get_stock_data, [symbol], period="1mo", interval="1d")
                    if hist is None or hist.empty or len(hist) < 2:
                        continue

                    # Average volume of the previous 20 daily candles (exclude today)
                    col_name = symbol if symbol.endswith(".NS") else symbol
                    avg_vol = hist[col_name]["Volume"].iloc[:-1].tail(20).mean()
                    if not avg_vol or avg_vol <= 0:
                        continue

                    live = get_live_price(symbol) or {}
                    today_vol = live.get("volume") or int(hist[col_name]["Volume"].iloc[-1])
                    vol_ratio = today_vol / avg_vol
                    if vol_ratio > 1.5:  # 1.5x average volume
                        price = live.get("price") or float(hist[col_name]["Close"].iloc[-1])
                        change = live.get("changePercent")
                        if change is None:
                            change = ((hist[col_name]["Close"].iloc[-1] - hist[col_name]["Close"].iloc[-2]) / hist[col_name]["Close"].iloc[-2]) * 100
                        all_alerts.append({
                            "symbol": symbol,
                            "price": round(price, 2),
                            "change": round(change, 2),
                            "volume": int(today_vol),
                            "avgVolume": int(avg_vol),
                            "volumeRatio": round(vol_ratio, 2),
                            "signal": "BUY" if change > 0 and vol_ratio > 2 else ("SELL" if change < 0 and vol_ratio > 2 else "WATCH")
                        })
                except Exception:
                    continue

        all_alerts.sort(key=lambda x: x["volumeRatio"], reverse=True)
        return {"alerts": all_alerts[:10], "timestamp": datetime.now().isoformat()}

    except Exception as e:
        return {"alerts": [], "error": str(e)}


@app.get("/api/portfolio/live-pnl")
async def get_portfolio_live_pnl(auth: bool = Depends(verify_api_key)):
    """Get live P&L for portfolio holdings"""
    try:
        from core.portfolio import get_portfolio
        holdings = get_portfolio()

        total_invested = 0
        total_current = 0
        holdings_with_pnl = []

        for holding in holdings:
            symbol = holding.get("symbol", "")
            buy_price = holding.get("buyPrice", 0)
            quantity = holding.get("quantity", 0)

            try:
                quote_symbol = symbol if symbol.endswith(".NS") else f"{symbol}.NS"
                quote = get_live_price(quote_symbol) or {}
                current_price = quote.get("price") or buy_price
                invested = buy_price * quantity
                current_value = current_price * quantity
                pnl = current_value - invested
                pnl_percent = ((current_value - invested) / invested * 100) if invested > 0 else 0

                total_invested += invested
                total_current += current_value

                holdings_with_pnl.append({
                    "symbol": symbol,
                    "buyPrice": buy_price,
                    "currentPrice": round(current_price, 2),
                    "quantity": quantity,
                    "invested": round(invested, 2),
                    "currentValue": round(current_value, 2),
                    "pnl": round(pnl, 2),
                    "pnlPercent": round(pnl_percent, 2)
                })
            except Exception:
                holdings_with_pnl.append({
                    "symbol": symbol,
                    "buyPrice": buy_price,
                    "currentPrice": buy_price,
                    "quantity": quantity,
                    "invested": round(buy_price * quantity, 2),
                    "currentValue": round(buy_price * quantity, 2),
                    "pnl": 0,
                    "pnlPercent": 0
                })

        total_pnl = total_current - total_invested
        total_pnl_percent = ((total_current - total_invested) / total_invested * 100) if total_invested > 0 else 0

        return {
            "holdings": holdings_with_pnl,
            "summary": {
                "totalInvested": round(total_invested, 2),
                "totalCurrent": round(total_current, 2),
                "totalPnL": round(total_pnl, 2),
                "totalPnLPercent": round(total_pnl_percent, 2)
            },
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        return {"holdings": [], "summary": {}, "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting StockPulse Pro on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
