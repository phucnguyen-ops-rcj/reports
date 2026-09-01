---
paths:
  - "tests/**/*.py"
---

# Testing

- Signal integration tests live in `tests/test_signal_client.py` and skip automatically when `SIGNAL_TEST_SENDER` (or `SIGNAL_SENDER` in `.env`) is unset — no extra setup needed
- Use `scope="module"` for the `client` fixture (one SignalClient per test module, not per test)
- Use `tmp_path` (pytest built-in) for temporary file attachments
- Assert Signal responses with: non-empty dict containing at least one of `timestamp`, `messageId`, `success`, `message`
- Env vars checked in order: `SIGNAL_TEST_SENDER` → `SIGNAL_SENDER` from `.env` via `app_settings`
