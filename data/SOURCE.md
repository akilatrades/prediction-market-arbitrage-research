# Archived market-data provenance

This folder holds a **read-only historical price dataset** from public Kalshi NBA contracts (2025–2026). It is copied here for a fully independent reproducible research workflow.

- Source snapshot: `akilatrades/sports-market-maker` commit `c29873bd0caab66ad03e76994d8f661d6e7d65c3`.
- Original files: `data/kalshi_history/{markets,candles}_{KXNBAPTS,KXNBAREB,KXNBAAST,KXNBA3PT}.parquet`.
- Transfer process: read-only GitHub Actions GET; **no commits or changes** to the source repo.
- Content: public market metadata and hourly historical bid/ask candles, **no account fills, secrets, positions, or private trading strategy code**.
- Scope: market-data archive for price-screen research; no claims of executable order-book depth or settlement-rule equivalence.

The provenance of these price files is acknowledged openly. After the one-time import, the independently hosted backtest reads the copies **inside this repository only**.
