
import json
from pathlib import Path

_config_file = Path(__file__).resolve().parents[2] / "config.json"

with open(_config_file) as f:
    _data = json.load(f)

SYMBOL_MAPPING = _data["symbol_mapping"]
STRATEGY_NAME_MAPPING = _data["strategy_name_mapping"]
CATEGORY_STRATEGY_MAPPING = {k: set(v) for k, v in _data["category_strategy_mapping"].items()}
ANALYSIS_DATA_COLUMNS = _data["analysis_data_columns"]
FINAL_COLUMNS = _data["final_columns"]
THRESHOLDS = _data["thresholds"]