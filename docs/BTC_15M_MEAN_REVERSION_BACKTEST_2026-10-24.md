# Bitcoin 15-minute mean-reversion backtest — completed 2026-10-24

**Status: research only, NOT approved for funding or automated trading.**

## Executive result

A 4-hour z-score filter combined with two prior same-direction 15-minute candles achieved **801 correct directional forecasts in 1,433 held-out signals (55.90%)** in July–September 2026. This was the best of five tested signal rules. The result is **directional accuracy on Binance spot BTC/USDT candles**, not prediction-market executable P&L. Selecting the best among multiple rules adds selection bias; this finding needs a fresh locked-rule forward evaluation.

- GitHub Actions run: https://github.com/akilatrades/prediction-market-arbitrage-research/actions/runs/40148361260
- Executable code: [tests/test_btc_15m_mean_reversion.py](../tests/test_btc_15m_mean_reversion.py)
- Machine-readable output: [results/btc_15m_reversion_oos_2026-07_to_2026-09.json](../results/btc_15m_reversion_oos_2026-07_to_2026-09.json)
- Data: Binance public BTCUSDT 15m spot klines, https://data.binance.vision/ ; 61,248 valid 15-minute candles, zero missing archive months, zero internal gaps.

## Research design

- Training: 2025-01-01 to 2026-06-30 UTC, 52,400 eligible windows (16-bar indicator warm-up).
- Out of sample: 2026-07-01 to 2026-09-30 UTC, 8,832 windows.
- Direction labels: whether the next BTCUSDT *spot* candle closes strictly higher than it opens.
- Signals calculated exclusively from completed earlier candles (no known look-ahead).
- Trade hypothesis: predict the next 15-minute window's binary up/down settlement. No actual order placement, matched historical contract ask, or limit fill is assumed.
- Score: correct predictions / eligible signals, with 95% Wilson intervals for binomial proportions (independence approximation).

## Out-of-sample results

| Predictor | Signals | Correct | Accuracy | Approximate 95% CI |
|---|---:|---:|---:|---|
| Fade previous bar | 8,832 | 4,534 | 51.34% | 50.29–52.38% |
| Fade two prior same-direction bars | 4,298 | 2,299 | 53.49% | 52.00–54.98% |
| 16-bar log-price z-score ≥1.5 / ≤−1.5 | 2,348 | 1,289 | 54.90% | 52.88–56.90% |
| 16-bar log-price z-score ≥2 / ≤−2 | 1,000 | 554 | 55.40% | 52.30–58.45% |
| **Two same-direction bars + z-score ≥1.5 in same direction** | **1,433** | **801** | **55.90%** | **53.31–58.45%** |

For the combination filter, the month-by-month record was 264/458 (57.64%) July, 276/503 (54.87%) August and 261/472 (55.30%) September.

## Conditional probability model

A simple smoothed conditional-frequency model trained before July used the last two candle directions and a three-bin z-score (12 cells, shrinkage toward a 50% prior). Held-out Brier score was **0.249059**, versus **0.250000** from always forecasting 50%: a *modest* improvement. When the fitted model estimated probability above 55% on one side, 994 of 1,782 held-out directions were correct (**55.78%**). This is not a venue-calibrated executable fair-value model.

## Illustrative prediction-market economics

**These figures are mathematical what-ifs, NOT real achieved returns**. Suppose a buy order for the combined signal's predicted outcome could execute at a fixed ask, it always filled, the proxy candle label exactly matched the contract's actual settlement, and the position was held to settlement. At 55.8967% empirical accuracy, estimated average net payout per share would be:

| Hypothetical buy price | Polymarket crypto taker fee at this price | Hypothetical mean net payout per contract |
|---:|---:|---:|
| 50¢ | 1.75¢ | **+4.15¢** |
| 53¢ | 1.74¢ | **+1.15¢** |
| 55¢ | 1.73¢ | **−0.84¢** |

Fee formula used for illustration: `fee = 0.07 × price × (1 − price)` (https://help.polymarket.com/en/articles/13364478-trading-fees). For the observed win rate, the theoretical break-even ask is approximately **54.16¢** after this taker fee, **before** slippage, order-book depth limits, label discrepancies, adverse selection, or uncertainty margin.

**Even if all hypotheticals held exactly, 1,433 single-share signals at 53¢ would amount to only about $16.52 estimated total profit across three months.** It is not a claim that this volume or fill quality was attainable; multiply-by-size scaling is unverified.

## Independent one-day Polymarket settlement cross-check

A public Marketlens sample of June 15, 2026 contains 96 Polymarket BTC Up/Down 15-minute settlements (https://github.com/marketlenstrade/polymarket-historical-data/tree/main/bitcoin-5m-15m-hourly-2026-06-15).

- Fade one prior 15m market: 52/95 = 54.74%.
- Fade two same-direction prior 15m markets: 23/42 = 54.76%.
- Fade three prior same-direction markets: 11/19 = 57.89%.

These samples are far too small to verify sustainable edge. Not all sampled contracts had nonzero traded volume and these tests used settled outcomes, not historical executable asks.

## What prevents deployment

1. Binance 15-minute spot candles **do not equal** Chainlink/CF Benchmarks contract resolution. Re-label each window using the *exact oracle and contract rule*. Check near-flat windows and exceptional settlement cases.
2. Obtain venue-specific historical **best ask, depth and trade timestamps** at the exact time the signal would be actionable. Validate that the fill price is genuinely available; a fixed 50¢/53¢ assumption is not a backtest of actual trades.
3. Apply venue-accurate transaction fees, partial fills, latency, slippage, order rejections, and maker queue effects.
4. Lock the combined rule; run a new chronologically separate forward test (for example, October onward) without further tuning, including month-by-month variability and uncertainty accounting for serial dependence/multiple testing.
5. Validate quote-calibrated expected value and walk-forward drawdown. Deploy *paper or minimal-capital* validation only after a positive executable net expectancy, not merely a higher-than-50% directional hit rate.

## Reproduction

The committed, read-only unittest downloads monthly BTCUSDT 15-minute CSV archives and computes each rule and its held-out accuracy. It does not use trading keys or account access. Run `python -m unittest discover -s tests -v` in the repository (the existing GitHub Actions workflow runs it automatically). Source revisions and input-date ranges must be pinned for future audits.
