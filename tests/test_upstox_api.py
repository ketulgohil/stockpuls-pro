from fastapi.testclient import TestClient
from main import app
from core.auth import get_api_key

client = TestClient(app)

def test_upstox_status_endpoint():
    response = client.get("/api/upstox/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "token_configured" in data

def test_paper_portfolio_endpoint():
    response = client.get("/api/upstox/paper/portfolio", headers={"X-API-Key": get_api_key()})
    assert response.status_code == 200
    data = response.json()
    assert "virtual_cash" in data or "cash" in data
    assert "positions" in data

def test_upstox_quotes_endpoint():
    response = client.get("/api/upstox/quotes")
    assert response.status_code == 200
    data = response.json()
    assert "quotes" in data

def test_upstox_quote_symbol_endpoint():
    response = client.get("/api/upstox/quote/RELIANCE")
    assert response.status_code == 200
    data = response.json()
    assert "symbol" in data
    assert "buy" in data
    assert "sell" in data

def test_upstox_scanners_endpoints():
    r1 = client.get("/api/upstox/scanner/orb")
    assert r1.status_code == 200
    assert "breakouts" in r1.json()

    r2 = client.get("/api/upstox/scanner/signals")
    assert r2.status_code == 200
    assert "signals" in r2.json()

def test_paper_trading_order_flow():
    # Reset portfolio first
    reset_resp = client.post("/api/upstox/paper/reset?initial_capital=500000.0", headers={"X-API-Key": get_api_key()})
    assert reset_resp.status_code == 200

    # Place order
    order_payload = {
        "symbol": "RELIANCE",
        "quantity": 10,
        "stop_loss": 2400.0,
        "target": 2600.0,
        "notes": "Test order",
        "entry_price": 2500.0
    }
    order_resp = client.post("/api/upstox/paper/order", json=order_payload, headers={"X-API-Key": get_api_key()})
    assert order_resp.status_code == 200
    pos = order_resp.json().get("position", {})
    assert pos.get("status") == "OPEN"
    pos_id = pos.get("id")

    # Close position
    close_resp = client.post(f"/api/upstox/paper/close/{pos_id}", json={"exit_price": 2550.0, "reason": "MANUAL"}, headers={"X-API-Key": get_api_key()})
    assert close_resp.status_code == 200
    closed_pos = close_resp.json().get("position", {})
    assert closed_pos.get("status") == "CLOSED"
    assert closed_pos.get("realized_pnl") > 0

def test_backtest_endpoint():
    resp = client.post("/api/upstox/backtest", json={"symbol": "RELIANCE", "period": "1d"})
    assert resp.status_code == 200
    data = resp.json()
    assert "total_trades" in data
    assert "win_rate" in data

def test_market_depth_endpoint():
    resp = client.get("/api/market/depth/RELIANCE")
    assert resp.status_code == 200
    data = resp.json()
    assert "symbol" in data
    assert "bids" in data or "buy" in data
    assert "asks" in data or "sell" in data
