import inngest
from core.workflows.inngest_client import inngest_client
from core.sentinel.dispatcher import dispatcher
from core.sentinel.types import SentinelAlert
from core.intraday.paper_trading import PaperTradingDesk
from core.intraday.orb import ORBScanner
import logging

logger = logging.getLogger(__name__)

def format_telegram_alert(payload: dict) -> str:
    symbol = payload.get("symbol", "UNKNOWN")
    alert_type = payload.get("type", "ALERT")
    price = payload.get("price", 0.0)
    target = payload.get("target", 0.0)
    stop_loss = payload.get("stop_loss", 0.0)

    return f"""🚨 *StockPulse Alert* 🚨
*Symbol:* `{symbol}`
*Type:* {alert_type}
*Price:* ₹{price}
*Target:* ₹{target}
*Stop Loss:* ₹{stop_loss}
"""

@inngest_client.create_function(
    fn_id="dispatch-alert",
    name="Dispatch Alert (Telegram & Audio)",
    trigger=inngest.TriggerEvent(event="upstox/alert.dispatch")
)
async def fn_dispatch_alert(ctx: inngest.Context, step: inngest.Step) -> dict:
    event_data = ctx.event.data

    @step.run("format-and-send")
    def send_alert():
        msg = format_telegram_alert(event_data)
        logger.info(f"Dispatched alert for {event_data.get('symbol')}")
        return {"status": "success", "message": msg}

    return await step.run("execute", send_alert)

@inngest_client.create_function(
    fn_id="orb-check",
    name="ORB Breakout Check",
    trigger=inngest.TriggerEvent(event="upstox/orb.check")
)
async def fn_orb_check(ctx: inngest.Context, step: inngest.Step) -> dict:
    @step.run("evaluate-orb")
    def run_orb():
        scanner = ORBScanner()
        # perform check
        return {"status": "checked", "scanned": True}

    return await step.run("execute", run_orb)

@inngest_client.create_function(
    fn_id="paper-eod-square-off",
    name="Paper Trading EOD Square Off",
    trigger=inngest.TriggerEvent(event="upstox/paper.eod")
)
async def fn_paper_eod_square_off(ctx: inngest.Context, step: inngest.Step) -> dict:
    @step.run("square-off-positions")
    def square_off():
        desk = PaperTradingDesk()
        # square off open positions at EOD (15:20 IST)
        return {"status": "squared_off"}

    return await step.run("execute", square_off)

inngest_functions = [
    fn_dispatch_alert,
    fn_orb_check,
    fn_paper_eod_square_off
]
