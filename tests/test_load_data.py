from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.utils.load_data import load_pnl_data, load_trading_volume_data


def test_load_pnl_data_local_reads_csv(monkeypatch):
    captured: dict[str, object] = {}
    raw_df = pd.DataFrame([["spot", "strategy1", "BTC", 1, 0, 0, 0, 0, 0, 0, "0%", 0]])
    wrangled_df = pd.DataFrame({"ok": [1]})

    monkeypatch.setattr("src.utils.load_data.pd.read_csv", lambda path: raw_df)

    def fake_wrangle(df):
        captured["df"] = df
        return wrangled_df

    monkeypatch.setattr("src.utils.load_data.wrangle_pnl_data", fake_wrangle)

    result = load_pnl_data("local", "data/sample.csv")

    assert captured["df"] is raw_df
    assert result.equals(wrangled_df)


def test_load_pnl_data_api_fetches_and_saves(monkeypatch):
    captured: dict[str, object] = {}
    api_df = pd.DataFrame([{"market": "spot"}])
    wrangled_df = pd.DataFrame({"ok": [1]})

    monkeypatch.setattr(
        "src.utils.load_data.build_analysis_dataframe",
        lambda: api_df,
    )

    def fake_save_csv(df, out_dir, prefix):
        captured["save"] = (df, out_dir, prefix)
        return Path("data/net_pnl/generated.csv")

    monkeypatch.setattr("src.utils.load_data.save_csv", fake_save_csv)

    def fake_wrangle(df):
        captured["wrangle_df"] = df
        return wrangled_df

    monkeypatch.setattr("src.utils.load_data.wrangle_pnl_data", fake_wrangle)

    result = load_pnl_data("api")

    saved_df, out_dir, prefix = captured["save"]
    assert saved_df is api_df
    assert out_dir == Path("data") / "net_pnl"
    assert prefix == ""
    assert captured["wrangle_df"] is api_df
    assert result.equals(wrangled_df)


def test_load_trading_volume_data_local_reads_csv(monkeypatch):
    captured: dict[str, object] = {}
    raw_df = pd.DataFrame([["BTC", 1]])
    wrangled_df = pd.DataFrame({"ok": [1]})

    monkeypatch.setattr("src.utils.load_data.pd.read_csv", lambda path: raw_df)

    def fake_wrangle(df):
        captured["df"] = df
        return wrangled_df

    monkeypatch.setattr("src.utils.load_data.wrangle_trading_volume_data", fake_wrangle)

    result = load_trading_volume_data("local", "data/trading_volume.csv")

    assert captured["df"] is raw_df
    assert result.equals(wrangled_df)


def test_load_trading_volume_data_api_fetches_and_saves(monkeypatch):
    captured: dict[str, object] = {}
    api_df = pd.DataFrame([{"base": "BTC"}])
    wrangled_df = pd.DataFrame({"ok": [1]})

    class FakeKucoinClient:
        def get_history_volume(self, symbols, limit):
            captured["symbols"] = symbols
            captured["limit"] = limit
            return api_df

    monkeypatch.setattr("src.utils.load_data.KucoinClient", FakeKucoinClient)

    def fake_save_csv(df, out_dir, prefix):
        captured["save"] = (df, out_dir, prefix)
        return Path("data/trading_volume/generated.csv")

    monkeypatch.setattr("src.utils.load_data.save_csv", fake_save_csv)

    def fake_wrangle(df):
        captured["wrangle_df"] = df
        return wrangled_df

    monkeypatch.setattr("src.utils.load_data.wrangle_trading_volume_data", fake_wrangle)

    result = load_trading_volume_data("api", symbols=["BTC", "ETH"])

    saved_df, out_dir, prefix = captured["save"]
    assert saved_df is api_df
    assert out_dir == Path("data") / "trading_volume"
    assert prefix == ""
    assert captured["symbols"] == ["BTC", "ETH"]
    assert captured["limit"] == 100
    assert captured["wrangle_df"] is api_df
    assert result.equals(wrangled_df)
