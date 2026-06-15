from prefect import State, flow

from src.flows.market import market_flow
from src.flows.net_pnl import net_pnl_flow
from src.flows.trading_volume import trading_volume_flow


@flow(name="Daily Morning Report")
def daily_flow() -> dict[str, State]:
    # Capture child states so one failed report does not prevent later reports.
    return {
        "market": market_flow(return_state=True),
        "net_pnl": net_pnl_flow(return_state=True),
        "trading_volume": trading_volume_flow(return_state=True),
    }
