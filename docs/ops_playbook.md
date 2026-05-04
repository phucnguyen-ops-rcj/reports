# TOOLS.md - Ops Playbook

Do NOT execute commands. Substitute values from the user's question into the correct template and return the filled command exactly as shown.

---

## General Rules

- `token` is always UPPERCASE (e.g. `usdt` → `USDT`)
- `exchange` must be one of the supported values listed per endpoint
- `market` is required only for futures exchanges: `kcf`, `binf`, `fintradef`
- When a field is ambiguous, ask the user to clarify before returning the command
- If the user's request doesn't match any endpoint, say so
- Always return **both** the direct curl and the SSH EOF version, labeled clearly
- **CRITICAL:** The closing `EOF` must always be on its own line with NO leading spaces or indentation. Never indent it.
- **CRITICAL:** When the SSH template includes `${RCJ_OPS_BEARER_TOKEN}`, always use `<<EOF`, never `<<'EOF'`, so the local shell expands the bearer token before SSH sends the script.
- **CRITICAL:** For SSH templates that include `${RCJ_OPS_BEARER_TOKEN}`, prepend the local secret-loading prelude exactly as shown:
  ```sh
  set -a
  source /Users/nguyentienphuc/.openclaw/secrets.env
  set +a
  ```

---

## Endpoint 1 — GET /health

**When asked:** "is the server up", "health check", "ping the API"

**Direct:**
```sh
curl http://18.176.93.228/health
```

**SSH:**
```sh
ssh -q -T T1_newuser1 <<EOF
curl -sS http://18.176.93.228/health
EOF
```

---

## Endpoint 2 — POST /get-balance

**When asked:** "what's my balance", "check balance", "how much [token] do I have on [exchange]"

**Supported exchanges:** `kc`, `kcf`, `kucoin`, `kucoinf`, `bybit`, `byb`, `okx`, `gate`, `gateio`, `binance`, `bin`, `binf`, `binancef`, `bitget`, `mexc`, `fintrade`, `fintradef`

**Extract from question:**
- `exchange` — required, no default. If missing → ask: "Which exchange?"
- `account` — optional, default: `main`
- `token` — optional, default: `USDT`, always uppercase. NOT a secret — never mask it.
- `market` — required only for futures (`kcf`, `binf`, `fintradef`): `spot` or `perp`. If missing → ask: "spot or perp?"

**Direct:**
```sh
curl -X POST http://18.176.93.228/get-balance \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"exchange": "<exchange>", "account": "<account>", "token": "<token>"}'
```

**SSH:**
```sh
set -a
source /Users/nguyentienphuc/.openclaw/secrets.env
set +a

ssh -q -T T1_newuser1 <<EOF
curl -sS --fail -X POST http://18.176.93.228/get-balance \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"exchange":"<exchange>","account":"<account>","token":"<token>"}'
EOF
```

**Direct (futures):**
```sh
curl -X POST http://18.176.93.228/get-balance \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"exchange": "<exchange>", "account": "<account>", "token": "<token>", "market": "<market>"}'
```

**SSH (futures):**
```sh
set -a
source /Users/nguyentienphuc/.openclaw/secrets.env
set +a

ssh -q -T T1_newuser1 <<EOF
curl -sS --fail -X POST http://18.176.93.228/get-balance \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"exchange":"<exchange>","account":"<account>","token":"<token>","market":"<market>"}'
EOF
```

---

## Endpoint 3 — POST /run-transfer

**When asked:** "transfer", "move funds", "withdraw", "sub to main", "main to sub"

**Supported modes:**
| Mode | Description | Required extra fields |
|------|-------------|----------------------|
| `sub_to_main` | Sub-account → main | `sub_account_name` (kc) |
| `main_to_sub` | Main → sub-account | `sub_account_name` (kc) |
| `withdraw` | Withdraw to another exchange | `to_exchange` |
| `future_to_spot` | Futures → spot | `sub_account_name` (kcf) |
| `spot_to_future` | Spot → futures | `sub_account_name` (kcf) |
| `future_to_main` | Futures → main (kcf only) | `sub_account_name` |
| `main_to_future` | Main → futures (kcf only) | `sub_account_name` |
| `trading_to_funding` | Trading → funding (OKX only) | — |

**Extract from question:**
- `mode` — required. If missing → ask which mode
- `token` — required, always uppercase
- `from_exchange` — required
- `amount` — required, positive number
- `sub_account_name` — required for kc/kcf modes. If missing → ask for it
- `to_exchange` — required for `withdraw`. If missing → ask for it

**Validation:**
- `trading_to_funding` → OKX only
- `future_to_main` / `main_to_future` → kcf only

**Direct (basic):**
```sh
curl -X POST http://18.176.93.228/run-transfer \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"mode": "<mode>", "token": "<token>", "from_exchange": "<from_exchange>", "amount": <amount>}'
```

**SSH (basic):**
```sh
set -a
source /Users/nguyentienphuc/.openclaw/secrets.env
set +a

ssh -q -T T1_newuser1 <<EOF
curl -sS --fail -X POST http://18.176.93.228/run-transfer \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"mode":"<mode>","token":"<token>","from_exchange":"<from_exchange>","amount":<amount>}'
EOF
```

**Direct (with sub_account_name):**
```sh
curl -X POST http://18.176.93.228/run-transfer \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"mode": "<mode>", "token": "<token>", "from_exchange": "<from_exchange>", "amount": <amount>, "sub_account_name": "<sub_account_name>"}'
```

**SSH (with sub_account_name):**
```sh
set -a
source /Users/nguyentienphuc/.openclaw/secrets.env
set +a

ssh -q -T T1_newuser1 <<EOF
curl -sS --fail -X POST http://18.176.93.228/run-transfer \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"mode":"<mode>","token":"<token>","from_exchange":"<from_exchange>","amount":<amount>,"sub_account_name":"<sub_account_name>"}'
EOF
```

**Direct (withdraw):**
```sh
curl -X POST http://18.176.93.228/run-transfer \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"mode": "withdraw", "token": "<token>", "from_exchange": "<from_exchange>", "amount": <amount>, "to_exchange": "<to_exchange>"}'
```

**SSH (withdraw):**
```sh
set -a
source /Users/nguyentienphuc/.openclaw/secrets.env
set +a

ssh -q -T T1_newuser1 <<EOF
curl -sS --fail -X POST http://18.176.93.228/run-transfer \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"mode":"withdraw","token":"<token>","from_exchange":"<from_exchange>","amount":<amount>,"to_exchange":"<to_exchange>"}'
EOF
```

---

## Endpoint 4 — POST /run-monitor

**When asked:** "monitor", "show strategy", "stream monitor", "watch positions"

**Extract from question:**
- `update_time` — optional, default: `10`

**Note:** Streams SSE. Stays open until Ctrl+C.

**Direct:**
```sh
curl -N -X POST http://18.176.93.228/run-monitor \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"update_time": <update_time>}'
```

**SSH:**
```sh
set -a
source /Users/nguyentienphuc/.openclaw/secrets.env
set +a

ssh -q -T T1_newuser1 <<EOF
curl -N -sS --fail -X POST http://18.176.93.228/run-monitor \
 -H "Authorization: Bearer ${RCJ_OPS_BEARER_TOKEN}" \
 -H "Content-Type: application/json" \
 -d '{"update_time":<update_time>}'
EOF
```
