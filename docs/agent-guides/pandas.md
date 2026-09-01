---
paths:
  - "src/**/*.py"
---

# Pandas Patterns

## Column access
- Always use bracket notation for columns with special characters: `df["npnl_r+un"]`, `df["volume_$"]`, `df["npnl/volume_%"]`
- Use `df.loc[:, cols]` (not `df[cols]`) when you need an unambiguous `DataFrame` return type

## Column order contract
- `wrangle_pnl_data()` assigns `df.columns = ANALYSIS_DATA_COLUMNS` — raw CSV column order **must** match `config/net_pnl.json → analysis_data_columns` exactly
- If the upstream CSV format changes, update `analysis_data_columns` in the config first
- Same contract applies to `wrangle_trading_volume_data()` with `TRADING_VOLUME_DATA_COLUMNS`

## Type conversions in wrangle
- `df["npnl_r+un"] = df["npnl_r+un"].astype(float)`
- `df["npnl/volume_%"] = df["npnl/volume_%"].str.rstrip("%").astype(float) / 100`

## Utility functions (use these, don't reimplement)
- `map_column_with_fallback(df, source_col, target_col, mapping)` — maps values with original as fallback
- `extract_prefix_column(df, source_col, target_col, separator="-")` — extracts part before separator
- `calculate_ratio_column(df, numerator_col, denominator_col, target_col, scale=1.0)` — ratio with scale
- `aggregate_metric_columns(df, group_by_cols, metric_cols)` — groupby sum
- `filter_rows_below_threshold(df, value_col, threshold)` — filter rows below value

## Common patterns
```python
# GroupBy + transform (attach group total back to rows)
df["category_total_npnl"] = df.groupby("category")["npnl_r+un"].transform("sum")

# Sort (always use by= keyword for Pyrefly)
df.sort_values(by=["category_total_npnl", "strategy"], inplace=True, ascending=[True, True])

# Merge with fillna
df = df.merge(other, on=["product", "base"], how="left").fillna({"last_24h_usd_volume": 0})

# GroupBy + agg
summary = df.groupby(["product", "base"]).agg({"usd_volume_24h": "sum"}).reset_index()
```
