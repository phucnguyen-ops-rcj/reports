# Arbitrage Parameter Analysis

This tool uses public exchange data to recommend four simple arbitrage config
fields:

```json
{
  "maker_fill_sleep": 10,
  "taker_fill_sleep": 10,
  "maker_min_order_size": 10,
  "taker_min_order_size": 15
}
```

It currently supports public market data from Binance and KuCoin for `spot` and
`perp` markets.

## What The Tool Does

The tool is not trying to predict price. It is trying to answer a safer
execution question:

```text
For this exchange, market, symbol, and user size, what order size can we use
without causing too much slippage or trading too fast for the available
liquidity?
```

It checks:

- exchange minimum order rules
- current bid/ask spread
- order book depth near the mid price
- simulated taker slippage for candidate order sizes
- recent 1-minute turnover
- 24-hour quote volume

Then it recommends:

- `maker_min_order_size`
- `taker_min_order_size`
- `maker_fill_sleep`
- `taker_fill_sleep`

## Quick Start

Run a fast one-snapshot analysis:

```bash
uv run arb_param_analysis \
  --phase 1 \
  --maker-exchange binance \
  --maker-market spot \
  --maker-side buy \
  --taker-exchange kucoin \
  --taker-market perp \
  --taker-side sell \
  --base-currency BTC \
  --quote-currency USDT
```

Run a short simulation using repeated snapshots:

```bash
uv run arb_param_analysis \
  --phase 2 \
  --duration-s 300 \
  --interval-s 5 \
  --maker-exchange binance \
  --maker-market spot \
  --maker-side buy \
  --taker-exchange kucoin \
  --taker-market perp \
  --taker-side sell \
  --base-currency BTC \
  --quote-currency USDT \
  --output results/arb_param_analysis/btc_binance_kucoin.json
```

Phase 2 is preferred before changing production config because one order book
snapshot can be noisy.

## Model Config

The analyzer's policy values live in:

```text
src/config/arb_param_analysis.json
```

Use another config file with:

```bash
uv run arb_param_analysis \
  --model-config src/config/arb_param_analysis.json \
  --phase 2 \
  ...
```

These values are deliberately configurable because they are not market facts.
They are risk preferences. A small, conservative user and a large, aggressive
user should not use the same thresholds.

Current default:

```json
{
  "defaults": {
    "max_allowed_taker_slippage_bps": 5.0,
    "max_order_fraction_of_10bps_depth": 0.05,
    "max_order_fraction_of_1m_p10_volume": 0.2,
    "max_position_size_usdt": 200.0,
    "max_settle_size_usdt": 100.0,
    "update_order_frequency_s": 10.0,
    "min_useful_maker_usdt": 10.0,
    "min_useful_taker_usdt": 15.0,
    "candidate_sizes_usdt": [5, 10, 15, 20, 25, 50, 75, 100]
  },
  "order_size": {
    "maker": {
      "max_settle_fraction": 0.5,
      "max_position_fraction": 0.25
    },
    "taker": {
      "maker_min_multiplier": 1.2,
      "max_settle_fraction": 0.75,
      "max_position_fraction": 0.5
    }
  },
  "tier_thresholds": {
    "A": {
      "max_spread_bps": 5.0,
      "min_depth_10bps_usdt": 5000.0,
      "min_recent_1m_turnover_p10_usdt": 5000.0,
      "slippage_check_size_usdt": 50.0
    },
    "B": {
      "max_spread_bps": 15.0,
      "min_depth_10bps_usdt": 500.0,
      "min_recent_1m_turnover_p10_usdt": 500.0,
      "slippage_check_size_usdt": 25.0
    },
    "C": {
      "max_spread_bps": 50.0,
      "min_depth_10bps_usdt": 50.0,
      "min_recent_1m_turnover_p10_usdt": 50.0
    }
  },
  "sleep": {
    "multipliers_by_tier": {
      "A": 0.5,
      "B": 1.0,
      "C": 2.0,
      "D": 6.0
    },
    "min_sleep_s": 3,
    "max_sleep_s": 120
  }
}
```

### Config Meaning

| Field | Meaning |
|---|---|
| `max_allowed_taker_slippage_bps` | Maximum simulated taker slippage allowed. `5` means `0.05%`. |
| `max_order_fraction_of_10bps_depth` | Max fraction of visible 10 bps book depth one order may consume. `0.05` means 5%. |
| `max_order_fraction_of_1m_p10_volume` | Max fraction of weak 1-minute turnover maker orders may use. |
| `max_position_size_usdt` | Final position target or cap from the strategy config. |
| `max_settle_size_usdt` | Max settle size from the strategy config. |
| `min_useful_maker_usdt` | Below this, maker orders are considered too small to bother placing. |
| `min_useful_taker_usdt` | Below this, taker hedges are considered too small to bother sending. |
| `candidate_sizes_usdt` | Discrete order sizes to test against the book. |
| `maker.max_settle_fraction` | Maker order cannot exceed this fraction of `max_settle_size_usdt`. |
| `maker.max_position_fraction` | Maker order cannot exceed this fraction of `max_position_size_usdt`. |
| `taker.maker_min_multiplier` | Taker minimum must be at least this multiple of maker minimum. |
| `taker.max_settle_fraction` | Taker order cannot exceed this fraction of `max_settle_size_usdt`. |
| `taker.max_position_fraction` | Taker order cannot exceed this fraction of `max_position_size_usdt`. |
| `tier_thresholds.A/B/C.max_spread_bps` | Maximum spread allowed for that tier. |
| `tier_thresholds.A/B/C.min_depth_10bps_usdt` | Minimum weak-case 10 bps depth required for that tier. |
| `tier_thresholds.A/B/C.min_recent_1m_turnover_p10_usdt` | Minimum weak-case recent 1-minute turnover required for that tier. |
| `tier_thresholds.A/B.slippage_check_size_usdt` | Candidate size that must pass the taker slippage limit for the tier. |
| `sleep.multipliers_by_tier` | Multiplies `update_order_frequency_s` to produce fill sleep. |
| `sleep.min_sleep_s` | Lower bound for recommended sleep. |
| `sleep.max_sleep_s` | Upper bound for recommended sleep. |

### Position Size Example

If:

```json
{
  "max_position_size_usdt": 200,
  "order_size": {
    "maker": {"max_position_fraction": 0.25},
    "taker": {"max_position_fraction": 0.5}
  }
}
```

Then:

```text
maker position cap = 200 * 0.25 = 50 USDT
taker position cap = 200 * 0.50 = 100 USDT
```

Even if BTCUSDT liquidity can support much larger orders, the analyzer will not
recommend sizes above these caps unless you increase the fractions.

For slower accumulation, use smaller fractions:

```json
{
  "maker": {"max_position_fraction": 0.1},
  "taker": {"max_position_fraction": 0.15}
}
```

With a `$200` final position, that means:

```text
maker cap = 20 USDT
taker cap = 30 USDT
```

## Symbol Format

The command derives symbols automatically:

| Exchange | Market | Derived symbol for BTC/USDT |
|---|---|---|
| Binance | spot | `BTCUSDT` |
| Binance | perp | `BTCUSDT` |
| KuCoin | spot | `BTC-USDT` |
| KuCoin | perp | `XBTUSDTM` for BTC, otherwise usually `BASEUSDTM` |

Override if needed:

```bash
--maker-symbol BTCUSDT
--taker-symbol XBTUSDTM
```

KuCoin futures sizes are contract-based. The analyzer applies the contract
`multiplier` before calculating USDT depth and minimum notional estimates.

## Phase 1

Phase 1 fetches one market snapshot.

Use it for:

- quick checks
- checking if a symbol exists
- getting an initial estimate
- debugging exchange data

Do not rely only on Phase 1 for thin altcoins. A single snapshot may show fake
depth, temporary empty levels, or abnormal spread.

## Phase 2

Phase 2 repeats Phase 1 over a time window.

Example:

```bash
--duration-s 300 --interval-s 5
```

This means:

```text
Take one snapshot every 5 seconds for 300 seconds.
```

The tool then uses conservative statistics:

- p10 depth: low-end depth, useful for avoiding optimistic book estimates
- p50 spread: normal spread
- p90 slippage: bad but common slippage
- p10 1-minute turnover: low-end recent volume

This is better for deciding real parameters because it asks, "What happens when
liquidity is worse than normal?"

## Important Inputs

### `--max-allowed-taker-slippage-bps`

Default: `5`

Maximum allowed taker slippage in basis points.

One basis point is `0.01%`, so:

```text
5 bps = 0.05%
```

If a candidate taker order size creates more slippage than this, the tool will
not treat that candidate as safe.

### `--candidate-sizes`

Default:

```text
5,10,15,20,25,50,75,100
```

These are the USDT order sizes the simulator tests.

For small altcoins, use smaller candidates:

```bash
--candidate-sizes 5,10,15,20,25,30,40,50
```

For BTC or ETH, use larger candidates:

```bash
--candidate-sizes 10,25,50,75,100,150,200
```

### `--max-order-fraction-of-10bps-depth`

Default: `0.05`

The recommended order should not consume more than this fraction of visible
depth within 10 bps.

Example:

```text
10 bps depth = 1000 USDT
fraction = 0.05
max safe order from depth = 50 USDT
```

### `--max-order-fraction-of-1m-p10-volume`

Default: `0.2`

The maker order should not be too large compared with low-end recent 1-minute
turnover.

Example:

```text
p10 1m turnover = 100 USDT
fraction = 0.2
max maker size from volume = 20 USDT
```

### `--max-position-size-usdt`

Default: `200`

Copied from the strategy config. The tool avoids recommending minimum order
sizes that are too large compared with total allowed position.

### `--max-settle-size-usdt`

Default: `100`

Copied from the strategy config. The tool avoids recommending order sizes that
are too large compared with settlement size.

### `--update-order-frequency-s`

Default: `10`

Used as the base for fill sleep.

The tool maps liquidity tier to sleep:

| Tier | Sleep rule |
|---|---|
| A | `0.5 * update_order_frequency_s` |
| B | `1.0 * update_order_frequency_s` |
| C | `2.0 * update_order_frequency_s` |
| D | `6.0 * update_order_frequency_s` |

The final value is clamped between 3 and 120 seconds.

## Output

The command prints JSON.

The most important section is:

```json
{
  "recommendation": {
    "maker_tier": "B",
    "taker_tier": "C",
    "params": {
      "maker_fill_sleep": 10,
      "taker_fill_sleep": 20,
      "maker_min_order_size": 10,
      "taker_min_order_size": 15
    },
    "reasons": []
  }
}
```

Copy only the values inside `params` into the simple arbitrage config after
reviewing the metrics and reasons.

## Meaning Of Each Recommended Param

### `maker_min_order_size`

Minimum maker order size in USDT.

The tool keeps this above:

- exchange minimum notional
- `--min-useful-maker-usdt`

And below conservative caps from:

- 10 bps order book depth
- recent low-end 1-minute turnover
- max position size
- max settle size

### `taker_min_order_size`

Minimum taker order size in USDT.

The tool keeps this above:

- exchange minimum notional
- `--min-useful-taker-usdt`
- `maker_min_order_size * 1.2`

And it checks that the candidate does not exceed
`--max-allowed-taker-slippage-bps`.

### `maker_fill_sleep`

Seconds to wait after a maker fill.

The sleep is shorter for liquid markets and longer for thin markets. This helps
avoid repeatedly acting on stale order book or portfolio state.

### `taker_fill_sleep`

Seconds to wait after a taker fill.

The sleep is based on taker-side liquidity. If taker liquidity is thin, the tool
waits longer to reduce over-hedging and repeated slippage.

## Tier Meaning

Tier is user-specific. The same market can be safe for a small user and unsafe
for a larger user.

| Tier | Meaning | Typical action |
|---|---|---|
| A | Tight spread, deep 10 bps book, high 1m turnover | Larger orders, short sleep |
| B | Normal liquid market | Default-size orders, normal sleep |
| C | Thin but usable market | Small orders, longer sleep |
| D | Very thin or unstable market | Avoid or use very small orders |

The tier depends on:

```text
symbol + exchange + market + side + user risk settings
```

It is not a permanent label for the symbol.

## Practical Workflow

1. Run Phase 1 for the target symbol.
2. If Phase 1 errors, check symbol format or whether the market exists.
3. If Phase 1 works, run Phase 2 for 3-5 minutes.
4. Review:
   - spread
   - 10 bps depth
   - taker slippage by size
   - p10 1-minute turnover
   - recommendation reasons
5. Apply the recommended `params` only if the reasons make sense.
6. After trading, compare with real fills and adjust risk settings.

## Example For Thin Altcoin

```bash
uv run arb_param_analysis \
  --phase 2 \
  --duration-s 300 \
  --interval-s 5 \
  --maker-exchange kucoin \
  --maker-market spot \
  --maker-side buy \
  --taker-exchange binance \
  --taker-market spot \
  --taker-side sell \
  --base-currency KAIO \
  --quote-currency USDT \
  --candidate-sizes 5,10,15,20,25,30,40,50 \
  --max-allowed-taker-slippage-bps 5
```

If the output says Tier C or D, do not force larger order sizes. The market is
telling you that visible liquidity is limited.
