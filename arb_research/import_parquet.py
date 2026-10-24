"""Load an independent read-only snapshot of public Kalshi Parquet history.

The source files may come from public research archives; this module imports
only market metadata and timestamped prices, never a trading strategy or account.
"""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path


def maybe_float(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError):
        return None


def import_files(inputs, out):
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("This historical import requires pandas and pyarrow") from exc

    out.mkdir(parents=True, exist_ok=True)
    all_markets, all_quotes, sources, series_counts = [], [], [], {}
    for series, markets_path, candles_path in inputs:
        markets = pd.read_parquet(markets_path)
        candles = pd.read_parquet(candles_path)
        required_m = {"ticker", "event_ticker", "yes_sub_title", "floor_strike"}
        required_c = {"ticker", "end_ts", "yes_bid", "yes_ask"}
        if not required_m.issubset(markets.columns):
            raise ValueError(f"Missing market columns for {series}: {required_m - set(markets)}")
        if not required_c.issubset(candles.columns):
            raise ValueError(f"Missing candle columns for {series}: {required_c - set(candles)}")
        valid = set()
        for m in markets.to_dict("records"):
            if m.get("result") not in ("yes", "no"):
                continue
            floor = maybe_float(m.get("floor_strike"))
            if floor is None:
                continue
            ticker = str(m["ticker"])
            record = {
                "ticker": ticker,
                "market_type": "binary",
                "event_ticker": str(m["event_ticker"]),
                "yes_sub_title": str(m["yes_sub_title"]),
                "floor_strike": floor,
                "result": m.get("result"),
            }
            all_markets.append({"ticker": ticker, "series": series, "market": record})
            valid.add(ticker)
        seen = set()
        n = 0
        for r in candles.to_dict("records"):
            tk = r.get("ticker")
            if tk not in valid:
                continue
            bid = maybe_float(r.get("yes_bid"))
            ask = maybe_float(r.get("yes_ask"))
            end_ts = maybe_float(r.get("end_ts"))
            if (bid is None or ask is None or end_ts is None
                    or not (0 < bid <= ask < 1)):
                continue
            key = (tk, int(end_ts))
            if key in seen:
                continue
            seen.add(key)
            all_quotes.append({
                "ticker": tk, "series": series,
                "candle": {
                    "end_period_ts": int(end_ts),
                    "yes_bid": {"close_dollars": str(bid)},
                    "yes_ask": {"close_dollars": str(ask)},
                },
            })
            n += 1
        series_counts[series] = {"markets_saved": len(valid), "quote_rows_saved": n}
        sources.append({"series": series, "markets_file": markets_path.name,
                        "candles_file": candles_path.name})
    with (out / "markets.jsonl").open("w") as f:
        for item in all_markets:
            f.write(json.dumps(item) + "\n")
    with (out / "quotes.jsonl").open("w") as f:
        for item in all_quotes:
            f.write(json.dumps(item) + "\n")
    manifest = {
        "source": "independent copy of existing public Kalshi 2025-26 research archive",
        "series_counts": series_counts, "files": sources,
        "markets_selected": len(all_markets),
        "candles": len(all_quotes), "interval_minutes": 60,
        "imported_utc": datetime.now(timezone.utc).isoformat(),
        "historical_orderbook_depth_available": False,
        "paired_fills_verified": False,
        "settlement_rules_verified": False,
        "warning": "Hourly market closes are not simultaneous executable depth",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    if not all_quotes:
        raise RuntimeError("Imported zero authentic price quotes")
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", default="data/archive_copy")
    p.add_argument("--output", default="data/historical")
    p.add_argument("--series", nargs="+",
                   default=["KXNBAPTS", "KXNBAREB", "KXNBAAST", "KXNBA3PT"])
    args = p.parse_args()
    root = Path(args.input)
    inputs = []
    for series in args.series:
        market = root / f"markets_{series}.parquet"
        candle = root / f"candles_{series}.parquet"
        if not market.exists() or not candle.exists():
            raise RuntimeError(f"Missing independent raw snapshot: {series}")
        inputs.append((series, market, candle))
    import_files(inputs, Path(args.output))


if __name__ == "__main__":
    main()
