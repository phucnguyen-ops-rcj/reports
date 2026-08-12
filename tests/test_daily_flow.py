from prefect.states import Completed, Failed

from src.flows import daily


def test_daily_flow_runs_all_child_flows_when_one_fails(monkeypatch):
    calls = []

    def fake_market_flow(*, return_state):
        calls.append(("market", return_state))
        return Completed(message="market complete")

    def fake_net_pnl_flow(*, return_state):
        calls.append(("net_pnl", return_state))
        return Failed(message="net pnl failed")

    def fake_trading_volume_flow(*, return_state):
        calls.append(("trading_volume", return_state))
        return Completed(message="trading volume complete")

    monkeypatch.setattr(daily, "market_flow", fake_market_flow)
    monkeypatch.setattr(daily, "net_pnl_flow", fake_net_pnl_flow)
    monkeypatch.setattr(daily, "trading_volume_flow", fake_trading_volume_flow)

    states = daily.daily_flow.fn()

    assert calls == [
        ("market", True),
        ("trading_volume", True),
        ("net_pnl", True),
    ]
    assert states["market"].is_completed()
    assert states["net_pnl"].is_failed()
    assert states["trading_volume"].is_completed()


def test_child_flows_try_three_times_before_failing():
    assert daily.market_flow.retries == 2
    assert daily.trading_volume_flow.retries == 2
    assert daily.net_pnl_flow.retries == 2
