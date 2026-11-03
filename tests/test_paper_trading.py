import os
import pytest
from core.intraday.paper_trading import PaperTradingDesk

TEST_STORAGE = "data/test_paper_trading.json"

@pytest.fixture(autouse=True)
def clean_storage():
    if os.path.exists(TEST_STORAGE):
        os.remove(TEST_STORAGE)
    yield
    if os.path.exists(TEST_STORAGE):
        os.remove(TEST_STORAGE)

def test_paper_trade_lifecycle():
    desk = PaperTradingDesk(initial_capital=1000000.0, storage_file=TEST_STORAGE)

    # Check initial summary
    summary = desk.get_summary()
    assert summary["initial_capital"] == 1000000.0
    assert summary["cash"] == 1000000.0
    assert summary["invested"] == 0.0
    assert summary["open_positions_count"] == 0

    # Execute buy order
    pos = desk.execute_buy(
        symbol="RELIANCE",
        quantity=100,
        stop_loss=2400.0,
        target=2600.0,
        notes="Test ORB breakout",
        entry_price=2500.0
    )

    assert pos is not None
    assert pos["symbol"] == "RELIANCE"
    assert pos["quantity"] == 100
    assert pos["entry_price"] == 2500.0
    assert pos["status"] == "OPEN"
    assert "id" in pos

    # Verify cash deduction (1,000,000 - 250,000 = 750,000)
    summary_after_buy = desk.get_summary()
    assert summary_after_buy["cash"] == 750000.0
    assert summary_after_buy["invested"] == 250000.0
    assert summary_after_buy["open_positions_count"] == 1

    # Update MTM with unrealized profit
    events = desk.update_mtm({"RELIANCE": {"last_price": 2550.0}})
    assert len(events) == 0  # No SL or target hit

    summary_mtm = desk.get_summary()
    assert summary_mtm["unrealized_pnl"] == 5000.0  # (2550 - 2500) * 100
    assert summary_mtm["current_value"] == 255000.0

    # Update MTM with target hit (> 2600.0)
    events = desk.update_mtm({"RELIANCE": {"last_price": 2610.0}})
    assert len(events) == 1
    assert events[0]["event"] == "TARGET_HIT"
    assert events[0]["position_id"] == pos["id"]

    # Verify position is now closed and cash returned with profit
    summary_closed = desk.get_summary()
    assert summary_closed["open_positions_count"] == 0
    assert summary_closed["closed_positions_count"] == 1
    assert summary_closed["realized_pnl"] == 11000.0  # (2610 - 2500) * 100
    assert summary_closed["cash"] == 1011000.0

def test_stop_loss_trigger():
    desk = PaperTradingDesk(initial_capital=500000.0, storage_file=TEST_STORAGE)
    pos = desk.execute_buy(
        symbol="TCS",
        quantity=50,
        stop_loss=3450.0,
        target=3600.0,
        notes="Support test",
        entry_price=3500.0
    )

    # Trigger stop loss (ltp <= 3450)
    events = desk.update_mtm({"TCS": {"last_price": 3440.0}})
    assert len(events) == 1
    assert events[0]["event"] == "STOP_LOSS_HIT"
    assert events[0]["position_id"] == pos["id"]

    summary = desk.get_summary()
    assert summary["open_positions_count"] == 0
    assert summary["realized_pnl"] == -3000.0  # (3440 - 3500) * 50

def test_manual_close_position():
    desk = PaperTradingDesk(initial_capital=500000.0, storage_file=TEST_STORAGE)
    pos = desk.execute_buy(
        symbol="INFY",
        quantity=200,
        stop_loss=1450.0,
        target=1600.0,
        notes="Manual close test",
        entry_price=1500.0
    )

    closed_pos = desk.close_position(pos["id"], exit_price=1550.0, reason="MANUAL")
    assert closed_pos["status"] == "CLOSED"
    assert closed_pos["exit_price"] == 1550.0
    assert closed_pos["realized_pnl"] == 10000.0  # (1550 - 1500) * 200

    summary = desk.get_summary()
    assert summary["open_positions_count"] == 0
    assert summary["realized_pnl"] == 10000.0

def test_insufficient_cash():
    desk = PaperTradingDesk(initial_capital=10000.0, storage_file=TEST_STORAGE)
    with pytest.raises(ValueError, match="Insufficient cash"):
        desk.execute_buy(
            symbol="RELIANCE",
            quantity=100,
            stop_loss=2400.0,
            target=2600.0,
            notes="Too expensive",
            entry_price=2500.0
        )
