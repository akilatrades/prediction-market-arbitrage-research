# Prediction Market Arbitrage Research

Independent, **read-only** research into structural arbitrage on U.S.-accessible prediction markets. This is not a trading bot and does not access accounts, hold credentials, or place/cancel orders.

## Current experiment

A historical Kalshi price-screen asks whether YES at a lower player-stat threshold plus NO at a higher threshold could cost less than its minimum theoretical $1 payout. It compares matching timestamps, applies illustrative taker fees, and never represents an apparent candle-price inversion as an executable fill or proven profit.

Historical candles are **not** order-book depth and cannot verify same-moment two-leg execution. Settlement rules must be reviewed separately. See `.github/workflows/historical-backtest.yml` for the automated run.

Research is kept entirely separate from all live trading projects.
