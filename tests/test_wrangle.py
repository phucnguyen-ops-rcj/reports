from __future__ import annotations

import pandas as pd

from src.utils.constants import ANALYSIS_DATA_COLUMNS
from src.utils.wrangle import wrangle_pnl_data


def test_wrangle_pnl_data_normalizes_strategy_aliases():
    df = pd.DataFrame(
        [
            ["spot", "strategy42", "BTC", 0, 0, 0, 0, 0, 0, "0", "0.0000%", 0],
            ["spot", "strategy92", "ETH", 0, 0, 0, 0, 0, 0, "0", "0.0000%", 0],
            ["spot", "kucc92", "SOL", 0, 0, 0, 0, 0, 0, "0", "0.0000%", 0],
        ],
        columns=ANALYSIS_DATA_COLUMNS,
    )

    result = wrangle_pnl_data(df)

    assert result["strategy"].tolist() == ["strategy4-2", "strategy9-2", "kucc9-2"]
    assert result["base_strategy"].tolist() == ["strategy4", "strategy9", "kucc9"]
