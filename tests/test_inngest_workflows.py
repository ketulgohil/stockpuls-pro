import pytest
from core.workflows.inngest_client import inngest_client
from core.workflows.functions import inngest_functions

def test_inngest_configuration():
    assert inngest_client is not None
    assert inngest_client.app_id == "stockpulse-pro"
    assert len(inngest_functions) >= 3

@pytest.mark.asyncio
async def test_alert_dispatch_payload():
    from core.workflows.functions import format_telegram_alert
    msg = format_telegram_alert({
        "symbol": "RELIANCE",
        "type": "ORB_BREAKOUT",
        "price": 1300.0,
        "target": 1330.0,
        "stop_loss": 1280.0
    })
    assert "RELIANCE" in msg
    assert "1300.0" in msg
    assert "TARGET" in msg.upper()
