## Optional Step 2c - Stacker Config Update

Only fields you provide are changed.

> At least one optional field must be provided. Must call `/setup_stacker_config` first.

**Example:**
```bash
curl -X POST http://18.176.93.228/update_stacker_config \
  -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "exchanges": "kucoin",
    "base_ccy": "RAVE",
    "quote_ccy": "USDT",
    "max_price": 10.0,
    "sell_stackers": "[{price: 0.0610 original_quantity: 1000}]"
  }'
```
