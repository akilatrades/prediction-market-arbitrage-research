# Bitcoin prediction-market strategy sweep — Kalshi and Polymarket

Research completed 2026-10-24 (UTC workflow runs 2026-10-25). Read-only; no money deployed or live accounts accessed.

## Bottom line

A broad **predefined strategy family sweep**, not an exhaustive search of all theoretically possible strategies. Includes Bitcoin reversal/momentum, z-score thresholds, RSI, volatility spikes, quote momentum/reversion, imbalance and estimated fair-value dislocations. The largest public matched historical Polymarket YES/NO book sample found **no convincingly robust, net-profitable strategy**: modest apparent positive results were small, unstable across time, or relied on a *proxy* BTC opening price instead of the actual oracle. A smaller Kalshi sample had promising reversal results, but its highest return came from **only 36 observations**, with possible sampling and multiple-comparison bias; a later calendar holdout should be evaluated separately.

## Data and methodology

### Polymarket
- 2026-04-01 to 2026-04-26, public third-party 1-second YES and NO top-of-book snapshots: 2,246,174 rows and 2,443 valid, settled 15-minute markets.
- One-share taker hypothetical entry at first valid posted ask 120 to 150 seconds after contract start, requires displayed ask depth >= 1 share; settlement at binary payout, or later exit against the archived best bid approximately five and ten minutes after entry. When late exit quote missing, explicit settlement fallback, *not* a claimed early exit.
- Fees modeled as `0.07 * p * (1-p)` per transaction; fee history not individually confirmed for every market. Historical quotes are not guaranteed fills; no latency and depth beyond top of book, no slippage or size scaling.
- Signals derived from previously completed Binance BTCUSDT 15-minute bars and current public book fields. The fair-value model uses an *approximate first observed Binance window price*, NOT the exact Chainlink/Polymarket opening price; the apparent model results require a stricter oracle-grounded rerun.
- Data: https://github.com/Vinayak19112003/Polymarket-orderbooks
- Workflow: https://github.com/akilatrades/prediction-market-arbitrage-research/actions/runs/40150626615
- Code: [polymarket_btc_strategy_sweep.py](../research/polymarket_btc_strategy_sweep.py)
- Exact measurements: [polymarket_btc_strategy_sweep_april_2026.json](../results/polymarket_btc_strategy_sweep_april_2026.json)

| Polymarket strategy | Trades | Correct share | Simulated one-share-per-trade total net |
|---|---:|---:|---:|
| One-bar reversal | 2443 | 52.64% | -$28.41 |
| Two-bar reversal | 1144 | 52.88% | -$35.92 |
| Two-bar momentum | 1144 | 47.12% | -$13.05 |
| 1.5 z-score reversal | 642 | 55.76% | -$10.50 |
| 2.0 z-score reversal | 271 | 57.56% | -$4.11 |
| Follow 1.5 z-score momentum | 642 | 44.24% | -$16.74 |
| Two-bar plus 1.5 z-score reversal | 373 | 58.45% | +$0.97 |
| RSI reversion | 501 | 54.29% | -$10.16 |
| RSI trend following | 501 | 45.71% | -$11.75 |
| Volatility spike reversal | 114 | 56.14% | -$0.23 |
| Contract-price mean reversion >=5c | 1823 | 33.08% | -$73.34 |
| Contract-price momentum >=5c | 1823 | 66.92% | -$3.52 |
| Book imbalance follow | 1259 | 54.01% | +$3.71 |
| Book imbalance fade | 1259 | 45.99% | -$58.21 |
| Binance-anchor fair-value gap >=5c (**proxy**) | 825 | 44.48% | -$10.23 |
| Binance-anchor fair-value gap >=10c (**proxy**) | 211 | 50.24% | +$6.39 |

Sixteen distinct directional/market-quote strategy rules are listed above.

The fair-value proxy 10c gap strategy generated +$7.15 in the early half of April and -$0.76 in the late half. The imbalance-follow strategy generated -$1.93 in the early half and +$5.64 in the late half. Neither has stable evidence of an edge. With 1,259 observations, imbalance-follow net averaging only **+0.295¢ per contract** is fragile to execution costs.

For the common earlier fixed mid-window reversion strategies we independently backtested a 26-day one-share maker touch/through proxy. The combined-streak maker **cross-through indicator** yielded **-$9.41 across 312 hypothetical indicated fills**, NOT actual maker fills; see [previous venue results](BTC_EXECUTION_REAL_QUOTES_RESULT_2026-10-24.md).

The 5-minute early-exit variant was negative for every signal, including the few otherwise positive settlement signals. The 10-minute exit often had fallback to settlement when no bid existed; treat cautiously.

### Kalshi preliminary historical one-minute quote sample
- 320 sampled `KXBTC15M` markets from public Kalshi historical APIs (Aug 14–24, 2026). 291 had returned candle records; 271 provided usable signals and entry quotes; 29 returned no candles (many rate limits). One-minute YES bid and YES ask candle close values are *minute-level approximations*, NOT exact executable same-timestamp queue quotes.
- Entry after ~3-6 minutes, use previously completed Binance 15m bars only; one-contract fees rounded UP to 1¢ per order. Binary settlement vs archive winner; 8-minute exit at recorded later minute bid. For the NO side, executable quote is inferred by complementing YES bid/ask; not independent NO depth.
- Code: [kalshi_btc_strategy_sweep.py](../research/kalshi_btc_strategy_sweep.py)
- Workflow: https://github.com/akilatrades/prediction-market-arbitrage-research/actions/runs/40150557039
- Data: [kalshi_btc_strategies_august_sample_2026.json](../results/kalshi_btc_strategies_august_sample_2026.json)

| Kalshi strategy | n | Winner fraction | Simulated settlement net (one contract per entry) |
|---|---:|---:|---:|
| Fade previous spot bar | 271 | 51.29% | -$1.32 |
| Fade 2 same-direction bars | 147 | 54.42% | +$2.94 |
| Follow 2 same-direction bars | 147 | 45.58% | -$10.09 |
| Fade 1.5 z-score | 82 | 52.44% | +$0.57 |
| Fade 2.0 z-score | 36 | 66.67% | +$5.31 |
| Combined streak + 1.5 z-score | 56 | 58.93% | +$3.91 |
| Follow 1.5 z-score | 82 | 47.56% | -$4.58 |
| Contract price fade | 184 | 33.15% | -$7.66 |
| Contract price follow | 184 | 66.85% | -$1.31 |

**Interpretation:** The short Kalshi sample suggests some directional reversion in BTC, but only 36 trades made the z2 headline. The exploratory samples are not an adequately powered, independently chosen prospective strategy. The market maker / live fill experience from other repositories is *not* evidence these historical quote signals can fill profitably.

## What was NOT proven or tested

- Identical-timestamp Kalshi vs Polymarket cross-venue BTC YES/NO arbitrage: available tested datasets use different dates. Do not compare their prices across dates as a hedge.
- Matched same-venue BTC YES+NO simultaneous fills (risk-free combined arbitrage).
- Live queue-based maker execution on both venues, maker rebate capture, short borrow/funding, profit by scaling beyond one share, and exact applicable fee schedules.
- Oracle-calibrated volatility or Bayesian fair-value: needs exact Chainlink and CF Benchmarks timestamped series and venue settlement strike for every tested window.
- BTC price ladders, hourly, daily, 5-minute, weekly contracts not covered by this 15-minute Up/Down test.
- Statistically powered prospective holdout after locking strategy parameters and controlling selection bias.

## Decision

**No go for funding** based on these available tests. Further tests should prioritize a genuinely unseen later Kalshi period, correct venue oracle-derived fair value, and paired timestamp execution economics. Simple fixed technical signals alone are unlikely to yield serious-money returns on these small samples. Different markets, spreads, and fee structures can change the result; this study does not prove no profitable strategy exists.

All changes are in the independent research repo, not the live market-making bot.
