from prefect import flow

from src.flows.market import market_flow
from src.flows.net_pnl import net_pnl_flow
from src.flows.trading_volume import trading_volume_flow


@flow(name="Daily Morning Report")
def daily_flow() -> dict:
    # run all three flows in parallel as subflows
    market_future = market_flow()
    pnl_future = net_pnl_flow()
    volume_future = trading_volume_flow()

    return {
        "market": market_future,
        "net_pnl": pnl_future,
        "trading_volume": volume_future,
    }
