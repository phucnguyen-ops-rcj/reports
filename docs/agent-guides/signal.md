---
paths:
  - "src/**/*.py"
---

# Signal Client

## Instantiation
```python
from src.clients.signal import SignalClient
client = SignalClient()  # reads sender/base_url from app_settings automatically
```

## Send signature
```python
client.send(
    message,                  # str, Path, or list/tuple of str|Path
    attachments=png_path,     # optional: str, Path, or list/tuple
    recipient=recipient,      # phone number string, or None
    group_id=group_id,        # group ID string, or None
)
```

## Non-fatal pattern — always wrap in try/except
```python
try:
    client = SignalClient()
    client.send(report_text, attachments=png_path, recipient=recipient, group_id=group_id)
    logger.info("Report sent via Signal successfully.")
except Exception as exc:
    logger.error(f"Failed to send Signal message: {exc}", exc_info=True)
```
Signal failures must never prevent report files from being saved — catch and log, do not re-raise.

## Guard with feature flag
```python
if not app_settings.enable_signal_notifications:
    return  # skip sending entirely
```

## Settings keys
- `signal_sender` — sending phone number
- `signal_recipient` — recipient phone number (optional)
- `signal_group_id` — Signal group ID
- `signal_base_url` — signal-cli REST API base URL
- `enable_signal_notifications` — feature flag to disable sending
