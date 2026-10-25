# Bitcoin mean reversion traded through prediction-market YES/NO contracts

**Study completed:** 2026-10-24 (UTC run: 2026-10-25)

## Question

Can a simple historical Bitcoin price mean-reversion signal be monetized by buying Polymarket BTC 15-minute Up/Down outcome contracts **and selling before settlement**, instead of holding binary payouts to resolution?

## Backtest design

- Archive: 26 days of one-second recorded Polymarket BTC 15m YES and NO order books (Apr 1–26, 2026), sourced from https://github.com/Vinayak19112003/Polymarket-orderbooks at pinned commit `280a29b9b818cc742c096af81c62e4bf899d44dc`.
- Binance BTCUSDT spot 15m OHLCV used strictly to compute signals from **prior completed** bars. Exact Polymarket settlement/oracle differs from Binance but early-exit P&L is marked using recorded outcome token bids, not the spot price.
- Entry: purchase at first eligible real YES or NO best ask between +60 and +90 seconds after contract opens; require displayed ask size at least one share.
- Exit: sell one share at *subsequent recorded best bid* with displayed bid size at least one share; ignore bids within 2 sec of simulated entry; allow up to 15 sec after scheduled exit, subject to remaining market life.
- Exit variants: TP +6¢ and SL −8¢ within 5 min; TP +8¢ and SL −8¢ within 8 min; TP +10¢ and SL −10¢ within 10 min; scheduled exits at 5, 10, 13 min after purchase.
- Both entry and exit modeled as taker orders charged `0.07 * price * (1-price)` per contract. Historical per-market fees, latency, actual fills and all other costs unverified.
- For a missing qualifying late exit bid, the scenario is *marked at its actual binary settlement* and charges entry fee; this is explicitly not evidence an exit took place.
- 2,246,174 order-book rows examined; 2,522 contract windows seen; 373 one-share positions in combined signal, and 2,160 signal positions over the three analyzed variants. The combined 373 cohort differs from the prior settlement-only study's 370 because entry-book eligibility filters are not identical.

## Combined BTC reversal signal results

Signal: previous two completed Binance 15m candles same direction and absolute 16-bar log-price z-score >= 1.5 in same direction; trade the **opposite** outcome token.

| Exit plan | n | Profitable trade fraction | Mean net/share | Total simulated net, 1 share | Missing bid fallback |
|---|---:|---:|---:|---:|---:|
| +6¢/-8¢, up to 5m | 373 | 49.87% | -4.665¢ | **-$17.40** | 0 |
| +8¢/-8¢, up to 8m | 373 | 46.11% | -4.563¢ | **-$17.02** | 0 |
| +10¢/-10¢, up to 10m | 373 | 47.45% | -4.350¢ | **-$16.23** | 0 |
| Sell 5m after entry | 373 | 50.40% | -2.803¢ | **-$10.46** | 0 |
| Sell 10m after entry | 373 | 55.50% | -1.128¢ | **-$4.21** | 9 |
| Sell 13m after entry | 373 | 57.37% | -0.776¢ | **-$2.90** | 57 |

The 5m time exit showed an approximately **+0.068¢ gross** price improvement but **−2.871¢ in modeled round-trip fees**, leaving **−2.803¢ average net**. TP/SL exit variants performed worse because profitable exits failed to sufficiently compensate for stop fills and round-trip costs.

The extended combined-strategy 10m outcome split was -$7.78 early April and +$3.57 late April. This variation is not enough to prove a durable profitable regime.

All one-share dollar totals are **scenario units**, not achieved P&L or claims of scalable displayed liquidity.

## Independent directional signal/hold-to-settlement research

- 61,248 Binance spot 15m candles, development before July 2026; out-of-sample July–September 2026: combined strategy 801/1,433 correct (55.90%).
- April 26-day *hold to settlement* Polymarket research: combined 215/370 (58.11%) with mean historical ask 56.57¢ and net **−$0.31** after modeled taker fee.
- This early-exit study asked whether quick in-contract exits improved returns: **none of the six exits tested did**.

## Conclusion / recommendation

**Do not deploy this particular unconditional Bitcoin price-reversal signal as a Polymarket or Kalshi trading bot.** It is not supported by positive simulated net P&L when using historical venue quotes.

A potentially better and as-yet-**untested** hypothesis is conditional **outcome-contract price mean reversion**: derive the probability of the Up or Down contract from the correct live settlement index, opening benchmark, time to close, realized/forecast short-horizon volatility and the order book. When the *contract executable ask* lies materially below that fair-value estimate and the deviation appears temporary, buy; exit at the subsequent **actual bid** if convergence recovers enough to pay entry + exit fees, spread, slippage and a safety margin. Do not use an unconditional 50–60% historical hit rate as contract fair value. For Kalshi, use CF Benchmarks and the specific contract's rules; for Polymarket, verify the oracle/contract's resolution specification.

Before funding: gather independent timestamped settlement-feed history, true historical quotes and sizes, maker queue/trades if passive, real per-market fees, and a chronologically untouched forward test. Account for API latency, market depth, min order sizes, missing quotes, statistical uncertainty and parameter selection.

## Reproduction

- [Early-exit backtest Python](../research/btc_contract_reversion_early_exit.py)
- [Early-exit detailed results](../results/btc_early_exit_26day_execution_2026-04.json)
- [Successful GitHub Actions run](https://github.com/akilatrades/prediction-market-arbitrage-research/actions/runs/40150236521)
- [Earlier settlement backtest comparison](BTC_EXECUTION_REAL_QUOTES_RESULT_2026-10-24.md)

Research is independent, read-only, no production market-maker modifications and no money deployed.
