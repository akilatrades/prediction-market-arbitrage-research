# Historical arbitrage backtest — October 24, 2026

## Result: no positive after-fee candidate observed

**This was the first successful real-data run.** Run [40133117087](https://github.com/akilatrades/prediction-market-arbitrage-research/actions/runs/40133117087) passed 10 unit tests, imported a read-only copy of archived 2025–26 public Kalshi NBA quotes and compared pairs of same-player nested thresholds.

| Measure | Result |
|---|---:|
| Archived NBA series | 4: points, rebounds, assists, threes |
| Market records imported | 77,307 |
| Valid timestamped candle rows | 439,041 |
| Unique multi-threshold player/event groups | 16,483 |
| Aligned historical two-contract price comparisons | 597,797 |
| Pair comparisons without both required historical prices | 622,645 (not imputed) |
| Positive price inconsistencies *before fees* | 7 player/timestamp observations |
| Positive **after** illustrative standard taker fees | **0** |
| Actual two-leg fills or realized dollar profit measured | **None** |

The seven observed candidate gross price differences were all **1¢ per pair**. Standard separate-leg taker fees made the illustrative net difference **negative 1–3¢ per pair** at a one-contract quantity on each side.

### The seven observed price discrepancies

| Series | Event date | Player | Lower → higher threshold | Gross difference | Net after assumed fees |
|---|---|---|---|---:|---:|
| NBA threes | May 1, 2026 | Paolo Banchero | 4+ / 5+ | +1¢ | −1¢ |
| NBA points | Feb 22, 2026 | Sam Hauser | 10+ / 15+ | +1¢ | −3¢ |
| NBA points | May 11, 2026 | Deandre Ayton | 15+ / 20+ | +1¢ | −1¢ |
| NBA points | May 21, 2026 | Jalen Brunson | 30+ / 40+ | +1¢ | −1¢ |
| NBA points | May 25, 2026 | Jaylon Tyson | 15+ / 20+ | +1¢ | −1¢ |
| NBA rebounds | Apr 30, 2026 | Onyeka Okongwu | 10+ / 12+ | +1¢ | −1¢ |
| NBA rebounds | May 3, 2026 | Cade Cunningham | 8+ / 10+ | +1¢ | −1¢ |

**No scenario in this sample produces an after-fee positive payoff** even if both legs could have filled at the sampled closing prices.

## What it means and does not mean

- The studied relationship was buying **YES on a lower threshold** and **NO on a higher threshold**, not trading a conventional single market's YES and NO.
- These are *hourly* bid/ask candle closes. A bid/ask on two markets with the same bar-end timestamp **need not have existed simultaneously**. No historical depth, queue priority, paired fills, or execution-delay simulation is present. The seven apparent price discrepancies may not have been tradable.
- The archive covers the 2025–26 NBA season and four specific player prop series, **not** every Kalshi or Polymarket market. The sample may contain in-game quotes: event start times were not independently verified or used to exclude in-game observations.
- The calculation uses the **standard illustrative Kalshi fee formula** and rounding. Fee overrides, special settlement terms, injury/DNP behavior, or fractional settlements need exact contract-rule checks before any actual trades.
- The result measures **no realized trading profit or loss**; it is a historical *price screen*, not a fully executable two-leg backtest.

## Decision

**No-go on allocating trading capital to straightforward NBA threshold-ladder taker arbitrage on this evidence.**

Research avenues still open:
1. Broader *logical/combinatorial* relationships across economic, political and other event markets;
2. Continuous second-level order-book capture (hourly bars can hide brief price inconsistencies);
3. A realistic simulator including fees, book depth, incomplete hedge fills and rule mismatches;
4. US-accessible cross-exchange opportunities once identical payout terms and both sides' liquidity can be verified.

Until live-forward data demonstrate a genuine after-fee opportunity and practical completion of both legs, **do not fund an arbitrage trader**.

The source snapshot is a read-only copy of public Kalshi historical Parquet records from an earlier research archive; all analysis code and workflows are in this independent repository. It does not change or execute any existing trading bot.
