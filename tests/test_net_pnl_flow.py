from pathlib import Path

import pandas as pd

from src.flows import net_pnl


def test_task_save_formats_category_total_npnl_only_for_png(monkeypatch, tmp_path):
    captured = {}
    final_df = pd.DataFrame(
        {
            "strategy": ["strategy1", "ETH"],
            "category_total_npnl": [-10_365.040000000003, [-1_200, -1_601]],
        }
    )

    monkeypatch.setattr(net_pnl.app_settings, "output_dir", str(tmp_path))

    def fake_save_report(report_text, out_dir):
        captured["report_text"] = report_text
        captured["report_out_dir"] = out_dir
        return Path(out_dir) / "report.txt"

    def fake_save_csv(df, out_dir, prefix):
        captured["csv_df"] = df.copy()
        captured["csv_out_dir"] = out_dir
        captured["csv_prefix"] = prefix
        return Path(out_dir) / "report.csv"

    def fake_net_pnl_to_png_styled(df, output_path, highlight_col=None):
        captured["png_df"] = df.copy()
        captured["png_output_path"] = output_path
        captured["png_highlight_col"] = highlight_col
        return output_path

    monkeypatch.setattr(net_pnl, "save_report", fake_save_report)
    monkeypatch.setattr(net_pnl, "save_csv", fake_save_csv)
    monkeypatch.setattr(net_pnl, "net_pnl_to_png_styled", fake_net_pnl_to_png_styled)

    png_path, csv_path, text_path = net_pnl.task_save.fn("report", final_df)

    assert png_path == tmp_path / "net_pnl" / "daily_net_pnl_by_strategy.png"
    assert csv_path == tmp_path / "net_pnl" / "report.csv"
    assert text_path == tmp_path / "net_pnl" / "report.txt"
    assert captured["csv_df"]["category_total_npnl"].tolist() == [
        -10_365.040000000003,
        [-1_200, -1_601],
    ]
    assert captured["png_df"]["category_total_npnl"].tolist() == [
        "-10,365.04",
        [-1_200, -1_601],
    ]
    assert captured["png_highlight_col"] == "npnl_r+un"
