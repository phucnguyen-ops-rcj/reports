# Type Checking (Pyrefly)

Pyrefly is the active type checker (configured via `[tool.pyrefly]` in `pyproject.toml` with `search-path = ["."]`). Known patterns to follow:

- **`df[list_of_cols]`** is typed as `DataFrame | Series` by pandas stubs — use `df.loc[:, cols]` to get an unambiguous `DataFrame`.
- **`DataFrame.sort_values`** requires `by=` as a keyword argument, not positional, for Pyrefly to resolve the correct overload.
- **`_to_float()` returns `float | None`** — use `(value or 0.0)` before arithmetic to narrow the type.
- **`datetime.now(tz)`** requires `tzinfo`, not `str` — use `ZoneInfo(app_settings.tz)` (stdlib, no stubs needed) instead of `pytz.timezone(app_settings.tz)`.
- **`pd.to_datetime("now") - Series`** — Pyrefly can't infer this returns `Series[Timedelta]`; suppress with `# pyrefly: ignore[missing-attribute]`.
- To silence a false positive inline: `# pyrefly: ignore[<error-code>]`
