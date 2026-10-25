# Bitcoin 15-minute mean reversion — actual recorded quote studies (2026-10-24)

## Decision

**Do not fund a BTC mean-reversion taker bot based on these results.** Binance BTC direction has a mild historical reversal pattern, but on the larger prediction-market historical sample the price already absorbs essentially all of the signal's advantage. The simulated one-share net result for the preferred combined signal is **−$0.31 across 370 eligible observations** after modeled taker fees. Hypothetical maker execution is also negative when restricted to periods in which subsequent books cross our resting quote, but those observations do not prove actual maker fills.

This is an independent **read-only** research project, not a trading bot.

## Data and timing

- Independent collector: Vinayak19112003/Polymarket-orderbooks, pinned commit `280a29b9b818cc742c096af81c62e4bf899d44dc`, 26 days, April 1–26 2026.
- Recorded observations parsed: **2,246,174** one-second rows. **2,443** markets had usable early quotes and observed settlement outcome.
- Signals calculated strictly from the previous **completed** 15-minute Binance BTCUSDT spot bars; never from the future settlement result.
- Entry market quote: first valid snapshot **60–90 seconds after** the contract opens. Observed YES and NO asks come from distinct respective token order books, not by synthetic complementation.
- One-share taker scenario: require displayed ask depth ≥1 share, assume immediate execution at quoted ask, hold contract until settlement, and deduct the illustrative crypto fee `0.07 * p * (1 - p)` per share. Actual historical fee schedule and fill latency were not individually verified.
- A user-executable strategy would need to confirm minimum order sizing and the exact contract settlement feed; one-share testing is a measurement unit, not assurance that a one-share live order can be placed.
- The older directional signal tests were selected after inspecting some of this calendar period: this venue-price sample is **retrospective research**, not a pristine out-of-sample evaluation of model selection.

## Taker results using one share per historical signal

| Strategy | Trades | Outcomes correct | Hit rate | Mean entry | Net P&L |
|---|---:|---:|---:|---:|---:|
| Reverse previous bar | 2,433 | 1,280 | 52.61% | 52.40¢ | **−$35.07** |
| Two-bar reversal | 1,140 | 602 | 52.81% | 54.36¢ | **−$36.52** |
| Z-score absolute ≥1.5 | 639 | 355 | 55.56% | 55.71¢ | **−$11.47** |
| Z-score absolute ≥2.0 | 270 | 155 | 57.41% | 56.98¢ | **−$3.24** |
| Combined two-bar reversal + z-score ≥1.5 | **370** | **215** | **58.11%** | **56.57¢** | **−$0.31** |

**The combined rule is directionally predictive but not net-profitable under the fee assumptions.** Average payout (58.108¢) less mean entry (56.568¢) leaves about 1.54¢ gross expected realized payout per historical signal. Modeled fees consume about 1.62¢; net about **−0.085¢ per 1-share trade**. No latency, slippage, cancellation or market impact is included, so live execution could perform worse.

### Does only buying cheaply help?

| Combined-filter taker selection | Trades | Correct | Avg ask | Mean net | Total net one-share |
|---|---:|---:|---:|---:|---:|
| Every available ask | 370 | 58.11% | 56.57¢ | −0.085¢ | −$0.31 |
| Ask ≤50¢ | 95 | 38.95% | 41.52¢ | −4.233¢ | −$4.02 |
| Ask ≤54¢ | 144 | 43.75% | 45.24¢ | −3.185¢ | −$4.59 |
| Ask ≤58¢ | 200 | 48.50% | 48.45¢ | −1.649¢ | −$3.30 |

Cheap contracts are cheaper because those directional outcomes are less likely. Screening only for a low ask significantly degraded this sample's outcome accuracy. Future work would need a *calibrated conditional probability model*, not an unconditional 58% prediction applied to every market.

### Stability check within the retrospective 26-day period

- April 1–13: 182 combined signals, 56.04% correct, mean 56.75¢ entry, **−$4.25** total.
- April 14–26: 188 combined signals, 60.11% correct, mean 56.39¢ entry, **+$3.94** total.

Large regime dependence; the signal was not consistently profitable throughout the month. This is *not* a clean model development/holdout experiment because the combined rule had already been examined in prior work.

## Indicative maker scenarios — not order fills

For each qualifying window, simulated posting a buy quote at the best bid, or improving it 1¢ if the spread was 2¢ or wider. Simulated orders rest **up to five minutes**. We checked the recorded best ask against the posted price, then calculated settlement P&L **only on indicated touched / crossed periods**. Order queue and actual passive executions are unavailable.

| Combined-filter maker proxy | Indicated quotes | Win rate conditional on indicator | Mean theoretical P&L / indicated share | Total theoretical P&L |
|---|---:|---:|---:|---:|
| Ask later touches posted quote | 328 | 53.35% | −1.927¢ | −$6.32 |
| Ask later passes through posted quote by ≥1¢ | **312** | **51.92%** | **−3.016¢** | **−$9.41** |

There were **373** combined-signal maker quotes eligible to be posted. A future book cross is **not evidence the hypothetical order would have filled**. The above numbers are adverse-selection indicators, not real maker P&L. Rebates excluded (unknown entitlement and allocation).

## Independent one-day June 15 quote experiment

A different Marketlens public archive supplied one day of 96 BTC 15-minute markets and 2,882 quote snapshots, with a trade-level archive used only for an indicative maker trade-through test. It applied the same prior-Binance-bar combined signal at the first eligible market snapshot (+30 to +180 seconds):

- Combined taker: **14** eligible directions, **9** correct, positive **+$1.32 total one-share** after the modeled fee.
- Purchase-price cap ≤54¢: **7** entries, 3 correct, approximately **+$0.005** (effectively zero).
- Maker trade-through proxy: 11 indicated events, 6 correct, about **+$0.60** hypothetical one-share total.

One day with 14 signals is too small and noisy to outweigh the negative, longer observed-quote record.

## Reproduce and verify

- [26-day reproducible source](../research/btc_multiday_orderbook_backtest.py)
- [26-day machine-readable results](../results/btc_yes_no_26day_execution_2026-04.json)
- [Successful 26-day GitHub Actions run](https://github.com/akilatrades/prediction-market-arbitrage-research/actions/runs/40149415308)
- [June 15 quote and maker-through research](../research/btc_execution_backtest.py)
- [Successful June 15 GitHub Actions run](https://github.com/akilatrades/prediction-market-arbitrage-research/actions/runs/40149182018)
- [Earlier multi-year spot directional test](BTC_15M_MEAN_REVERSION_BACKTEST_2026-10-24.md)

Underlying quoted data belongs to third-party collectors; historical fee model based on Polymarket's official fee documentation: https://help.polymarket.com/en/articles/13364478-trading-fees . The April 2026 fee schedule is not independently stored per market and is modeled rather than verified.

## Implication and proposed next validation

1. **No live-money allocation based on these simple mean-reversion signals.** No reliable net edge or serious-money scalability demonstrated.
2. If continuing, train a probability-calibrated fair-value model on both the current market quote and BTC information known *at the same instant*, with untouched later data and per-market fee schedules.
3. For passive orders, record actual public prints, order acceptance, ahead-of-us queue size, cancellations, and inventory changes; compare maker fills and adverse selection directly.
4. Validate real cost, time, one-sided event-risk, scale, max drawdown and maker rebate eligibility. Until then, never label book-touch scenarios as profit.
