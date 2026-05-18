import json
from pathlib import Path

_net_pnl_config_file = Path(__file__).resolve().parents[1] / "config" / "net_pnl.json"
# _trading_volume_config_file = Path(__file__).resolve().parents[1] / "config" / "trading_volume.json"
_trading_volume_config_file = Path(
    "/Users/nguyentienphuc/rcj/ops_bot/.docker-data/trading_volume.json"
)

with open(_net_pnl_config_file) as f:
    _data = json.load(f)

# net pnl analysis
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


# trading volume
with open(_trading_volume_config_file) as f:
    _data = json.load(f)
TRADING_VOLUME_DATA_COLUMNS = _data["trading_volume_data_columns"]
MONITORING_SYMBOLS = _data["monitoring_symbols"]
REQUIREMENT_VOLUME = _data["requirement_volume"]
# check every values is dictionary with keys "spot" and "perp"
for exchange, requirements in REQUIREMENT_VOLUME.items():
    # ALL MONITORING_SYMBOLS must have requirement volume defined, otherwise raise error
    for symbol in MONITORING_SYMBOLS:
        if symbol not in requirements:
            raise ValueError(
                f"All monitoring symbols must have requirement volume defined in REQUIREMENT_VOLUME. Missing: {symbol} in exchange {exchange}"
            )
