---
paths:
  - "src/**/*.py"
---

# Data Loading

## Entry points
```python
from src.utils.load_data import load_pnl_data, load_trading_volume_data

df = load_pnl_data(source="local", file_path="data/trades.csv")
df = load_trading_volume_data(source="local", file_path="data/volume.csv")
```
Both functions call the relevant `wrangle_*` function internally — callers always receive a wrangled DataFrame.

## Default file paths (from settings)
- P&L trades: `data/trades.csv` (`net_pnl_input_path`)
- Trading volume: `data/trading_volume.csv` (`trading_volume_input_path`)
- Input dir: `data/` (`input_dir`)
- Output dir: `results/` (`output_dir`)

## Column order contract
Raw CSV columns must match `ANALYSIS_DATA_COLUMNS` in `config/net_pnl.json` exactly — `wrangle_pnl_data()` blindly reassigns `df.columns`. If the source CSV changes, update the config first.

## Loss threshold
Symbols with `npnl_r+un < -1000` (from `config/net_pnl.json → thresholds.loss_pnl`) are flagged separately in the report.

## Symbol mapping
Raw symbols are normalised via `SYMBOL_MAPPING` in `config/net_pnl.json` (e.g. `"1000BONK"` → `"BONK"`). Unmapped symbols fall back to the original value.
