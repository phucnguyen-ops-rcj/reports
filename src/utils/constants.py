
SYMBOL_MAPPING = {
        "BONK": "BONK",
        "1000BONK": "BONK",
        "BEAT": "BEAT",
        "KBEAT": "BEAT",
        "SHIB": "SHIB",
        "1000SHIB": "SHIB"
}

STRATEGY_NAME_MAPPING = {
        "strategy1": "quoting",
        "strategy2": "FDV directional",
        "strategy3": "no name",
        "strategy4": "volume",
        "strategy4-2": "volume fintrade",
        "strategy5": "spot arb",
        # "strategy6": "un-known",
        "strategy7": "no name",
        "strategy8": "negative FR",
        "strategy9": "directional 1",
        "strategy9-2": "directional 2",
        "strategy10": "positive FR",
        "strategy11": "liquidity",
        "strategy12": "perp arb",
        "strategy13": "RFQ",
        "kucc4": "kucc4",
        "kucc4-2": "kucc4"
    }

CATEGORY_STRATEGY_MAPPING = {
    "Quoting": {"strategy1"},
    "FDV": {"strategy2"},
    "FR": {"strategy8", "strategy10"},
    "Arb": {"strategy5", "strategy12"},
    "1sec": {"strategy11", "kucc4", "kucc4-2"},
    "Volume": {"strategy4", "strategy4-2"},
    "Directional": {"strategy9", "strategy9-2"},
    "RFQ": {"strategy13"},
}

ANALYSIS_DATA_COLUMNS = ["market", "strategy", "symbol", "volume_$", "net_position", "net_position_$", "rpnl", "unpnl", "rpnlwfees", "npnl_r+un", "npnl/volume_%", "trade_count"]
FINAL_COLUMNS = ["volume_$", "npnl_r+un", "net_position_$", "unpnl", "rpnlwfees"]

THRESHOLDS = {
    "loss_pnl": -1000
}