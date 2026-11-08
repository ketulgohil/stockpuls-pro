from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import json
import asyncio
from datetime import datetime
from api import (
    stocks, screener, signals, portfolio, sector, tools,
    news, backtest, market, compare, patterns,
    correlation, breadth, fundamentals, analysis, alerts, export, ai, gemini, advanced, more, features, gold, analytics,
    mutual_funds, currency, block_deals, quarterly_results, screener_strategies, downstox, sentinel, upstox_trading,
    exit, budget, risk, scanner, entry, timemachine, analyst, alerts, broker, institutional
)
import inngest.fast_api
from core.workflows.inngest_client import inngest_client
from core.workflows.functions import inngest_functions
from core.sentinel.dispatcher import dispatcher
from core.sentinel.engine import sentinel_engine
from core import upstox_data
from core.data_fetcher import get_stock_data, get_live_price

app = FastAPI(
    title="Indian Stock Market Analysis Platform",
    description="Technical analysis, screening, and signals for NSE/BSE stocks",
    version="5.0.0"
)

@app.on_event("startup")
async def startup_event():
    print("🚀 StockPulse Pro started successfully!")
    sentinel_engine.start()

@app.on_event("shutdown")
async def shutdown_event():
    sentinel_engine.stop()

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
app.include_router(alerts.router)
app.include_router(broker.router)
app.include_router(institutional.router)
app.include_router(more.router)
app.include_router(features.router)
app.include_router(gold.router)
app.include_router(analytics.router)
app.include_router(mutual_funds.router)
app.include_router(currency.router)
app.include_router(block_deals.router)
app.include_router(quarterly_results.router)
app.include_router(screener_strategies.router)
app.include_router(downstox.router)
app.include_router(sentinel.router)
app.include_router(upstox_trading.router)

app.mount("/static", StaticFiles(directory="static"), name="static")

inngest.fast_api.serve(app, inngest_client, inngest_functions)


# ===== WebSocket Live Price Streaming =====

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

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


@app.websocket("/ws/live-prices")
async def websocket_live_prices(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        # Receive symbols from client
        data = await websocket.receive_text()
        params = json.loads(data)
        symbols = params.get("symbols", [])

        if not symbols:
            symbols = ["^NSEI", "^NSEBANK", "^BSESN"]  # Default: NIFTY, BANKNIFTY, SENSEX

        # Start sending updates
        while True:
            try:
                prices_raw = upstox_data.get_quotes(symbols)
                prices = {
                    sym: {
                        "price": q["price"],
                        "change": q["change"],
                        "changePercent": q["changePercent"],
                    }
                    for sym, q in prices_raw.items()
                }

                await websocket.send_text(json.dumps({
                    "prices": prices,
                    "timestamp": str(datetime.now())
                }))
            except Exception:
                break

            await asyncio.sleep(10)
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
    return FileResponse("static/index.html")


@app.get("/api/market/status")
async def get_market_status():
    """Get current market status for NSE/BSE"""
    from datetime import datetime
    now = datetime.now()
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
        # Get top traded stocks from NIFTY 50
        symbols = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
                   "HINDUNILVR.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "KOTAKBANK.NS",
                   "LT.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "HCLTECH.NS",
                   "SUNPHARMA.NS", "TATAMOTORS.NS", "WIPRO.NS", "ULTRACEMCO.NS", "ONGC.NS"]

        alerts = []
        for symbol in symbols:
            try:
                hist = get_stock_data(symbol, period="1mo", interval="1d")
                if hist is None or hist.empty or len(hist) < 2:
                    continue

                # Average volume of the previous 20 daily candles (exclude today)
                avg_vol = hist["Volume"].iloc[:-1].tail(20).mean()
                if not avg_vol or avg_vol <= 0:
                    continue

                live = get_live_price(symbol) or {}
                today_vol = live.get("volume") or int(hist["Volume"].iloc[-1])
                vol_ratio = today_vol / avg_vol
                if vol_ratio > 1.5:  # 1.5x average volume
                    price = live.get("price") or float(hist["Close"].iloc[-1])
                    change = live.get("changePercent")
                    if change is None:
                        change = ((hist["Close"].iloc[-1] - hist["Close"].iloc[-2]) / hist["Close"].iloc[-2]) * 100
                    alerts.append({
                        "symbol": symbol.replace(".NS", ""),
                        "price": round(price, 2),
                        "change": round(change, 2),
                        "volume": int(today_vol),
                        "avgVolume": int(avg_vol),
                        "volumeRatio": round(vol_ratio, 2),
                        "signal": "BUY" if change > 0 and vol_ratio > 2 else ("SELL" if change < 0 and vol_ratio > 2 else "WATCH")
                    })
            except Exception:
                continue

        alerts.sort(key=lambda x: x["volumeRatio"], reverse=True)
        return {"alerts": alerts[:10], "timestamp": datetime.now().isoformat()}

    except Exception as e:
        return {"alerts": [], "error": str(e)}


@app.get("/api/portfolio/live-pnl")
async def get_portfolio_live_pnl():
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
