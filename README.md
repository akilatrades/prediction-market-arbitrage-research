# Prediction Market Arbitrage Research

Independent, **read-only** research into structural arbitrage on U.S.-accessible prediction markets. This is not a trading bot and does not access accounts, hold credentials, or place/cancel orders.

## Current experiment

A historical Kalshi price-screen asks whether YES at a lower player-stat threshold plus NO at a higher threshold could cost less than its minimum theoretical $1 payout. It compares matching timestamps, applies illustrative taker fees, and never represents an apparent candle-price inversion as an executable fill or proven profit.

Historical candles are **not** order-book depth and cannot verify same-moment two-leg execution. Settlement rules must be reviewed separately. See `.github/workflows/historical-backtest.yml` for the automated run.

Research is kept entirely separate from all live trading projects.

## First completed historical study (2026-10-24)

The [historical result](docs/HISTORICAL_BACKTEST_RESULT_2026-10-24.md) covers **597,797 matching historical NBA price-pair comparisons** across four player-prop series. Only **7** observations showed a positive gross threshold inversion, and **0** remained positive after illustrative standard taker fees. No real order fills or P&L were measured. **Not ready to fund.**

[Successful GitHub Actions run](https://github.com/akilatrades/prediction-market-arbitrage-research/actions/runs/40133117087) stores the raw quoted-price evidence and JSON result. The public data were copied read-only from a previously collected Kalshi archive, pinned to a historic commit; no production trading code is imported.
