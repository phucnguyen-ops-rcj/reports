
import json
from pathlib import Path

_config_file = Path(__file__).resolve().parents[1] / "config.json"

with open(_config_file) as f:
    _data = json.load(f)

SYMBOL_MAPPING = _data["symbol_mapping"]
STRATEGY_NAME_MAPPING = _data["strategy_name_mapping"]
STRATEGY_CATEGORY_MAPPING = _data["strategy_category_mapping"]
CATEGORY_STRATEGY_MAPPING = {}
for key, value in STRATEGY_CATEGORY_MAPPING.items():
    if value not in CATEGORY_STRATEGY_MAPPING:
        CATEGORY_STRATEGY_MAPPING[value] = [key]
    else:
        CATEGORY_STRATEGY_MAPPING[value].append(key)
ANALYSIS_DATA_COLUMNS = _data["analysis_data_columns"]
FINAL_COLUMNS = _data["final_columns"]
THRESHOLDS = _data["thresholds"]