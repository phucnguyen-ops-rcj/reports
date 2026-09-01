# Commands

All commands use `uv` as the runner. The package is installed in editable mode so `src.*` imports resolve correctly.

```bash
# Run a script directly
uv run -m src.scripts.net_pnl
uv run -m src.scripts.market
uv run -m src.scripts.trading_volume

# Or via CLI entry points (after install)
uv run market
uv run net_pnl
uv run trading_volume

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_signal_client.py

# Run a single test
uv run pytest tests/test_signal_client.py::test_send_text_message_to_recipient
```

Signal integration tests require a live signal-cli REST API and will skip automatically if `SIGNAL_SENDER` is not set.
