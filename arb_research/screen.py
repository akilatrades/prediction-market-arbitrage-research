"""Strict, conservative historical quote screen: NOT an execution backtest.

YES(lower threshold) plus NO(higher threshold) pays at least $1 only if the
exact market-resolution terms imply the higher event is a subset of lower.
Only pre-existing, equally timestamped bid/ask candle closes are compared.
"""
import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from pathlib import Path
from .archive import strike

FEE_RATE = Decimal("0.07")


def dec(value):
    try:
        item = Decimal(str(value))
        return item if item.is_finite() else None
    except (ValueError, InvalidOperation, TypeError):
        return None


def close(block):
    if not isinstance(block, dict):
        return None
    # Kalshi uses both schemas: archived 'close' (cents) and
    # modern 'close_dollars' (dollars). Do not silently mix them.
    if block.get("close_dollars") is not None:
        v = dec(block["close_dollars"])
    elif block.get("close") is not None:
        v = dec(block["close"])
        v = v / 100 if v is not None else None
    else:
        return None
    return v if v is not None and Decimal("0") < v < Decimal("1") else None


def candle(c):
    try:
        raw_time = c.get("end_period_ts") or c.get("end_period_at")
        if isinstance(raw_time, str) and not raw_time.isdigit():
            ts = int(datetime.fromisoformat(raw_time.replace("Z", "+00:00")).timestamp())
        else:
            ts = int(raw_time)
        bid, ask = close(c.get("yes_bid")), close(c.get("yes_ask"))
        if bid is None or ask is None or bid > ask:
            return None
        return ts, bid, ask
    except (ValueError, TypeError, OverflowError):
        return None


def taker_fee(price, quantity):
    raw = FEE_RATE * price * (1 - price) * quantity
    return raw.quantize(Decimal("0.01"), rounding=ROUND_CEILING)


def study(market_rows, quote_rows, quantity=1, period=60):
    if quantity < 1:
        raise ValueError("size must be positive")
    groups = defaultdict(list)
    valid_tickers = set()
    for row in market_rows:
        m = row["market"]
        parsed = strike(m)
        if parsed is None:
            continue
        player, threshold = parsed
        key = (row["series"], m["event_ticker"], player)
        groups[key].append((threshold, row["ticker"]))
        valid_tickers.add(row["ticker"])
    books = defaultdict(dict)
    all_rows = 0
    for row in quote_rows:
        ticker = row.get("ticker")
        if ticker not in valid_tickers:
            continue
        value = candle(row["candle"])
        if value is None:
            continue
        time, bid, ask = value
        books[ticker][time] = (bid, ask)
        all_rows += 1
    checks, missing, candidates = 0, 0, []
    unique_groups = 0
    for key, strikes in sorted(groups.items()):
        if len(strikes) < 2 or len({s for s, _ in strikes}) != len(strikes):
            continue
        unique_groups += 1
        strikes.sort()
        timestamps = sorted({t for _, tk in strikes for t in books[tk]})
        for t in timestamps:
            best = None
            for j, (lower, low_ticker) in enumerate(strikes):
                for higher, high_ticker in strikes[j + 1 :]:
                    low_price = books[low_ticker].get(t)
                    high_price = books[high_ticker].get(t)
                    if low_price is None or high_price is None:
                        missing += 1
                        continue
                    checks += 1
                    yes_ask = low_price[1]
                    no_ask = Decimal("1") - high_price[0]
                    gross = Decimal("1") - yes_ask - no_ask
                    if gross <= 0:
                        continue
                    total_fee = taker_fee(yes_ask, quantity) + taker_fee(no_ask, quantity)
                    net = gross * quantity - total_fee
                    item = {
                        "series": key[0], "event": key[1], "player": key[2],
                        "timestamp_utc": datetime.fromtimestamp(
                            t, tz=timezone.utc
                        ).isoformat(),
                        "buy_yes": low_ticker, "buy_no": high_ticker,
                        "lower_strike": lower, "higher_strike": higher,
                        "gross_cents_per_pair": float(100 * gross),
                        "illustrative_net_usd": float(net),
                        "positive_after_standard_fees": net > 0,
                        "confirmed_executable_trade": False,
                    }
                    if best is None or net > best[0]:
                        best = (net, item)
            if best:
                # One candidate per player/event/timestamp; nested pairs are not
                # independent opportunities.
                candidates.append(best[1])

    # A new episode only when a particular player/event has a gap larger
    # than one candle interval. This is NOT a confirmed quote lifetime.
    by_event = defaultdict(list)
    for row in candidates:
        by_event[(row["series"], row["event"], row["player"])].append(row)
    episodes = []
    interval_seconds = period * 60
    for key, rows in by_event.items():
        rows.sort(key=lambda x: x["timestamp_utc"])
        last_ts, current = None, []
        for row in rows:
            ts = datetime.fromisoformat(row["timestamp_utc"]).timestamp()
            if current and ts - last_ts > interval_seconds:
                episodes.append({
                    "event": list(key), "samples": len(current),
                    "first": current[0]["timestamp_utc"],
                    "last": current[-1]["timestamp_utc"],
                    "best_net_usd": max(x["illustrative_net_usd"] for x in current),
                })
                current = []
            current.append(row)
            last_ts = ts
        if current:
            episodes.append({
                "event": list(key), "samples": len(current),
                "first": current[0]["timestamp_utc"],
                "last": current[-1]["timestamp_utc"],
                "best_net_usd": max(x["illustrative_net_usd"] for x in current),
            })
    return {
        "classification": "HISTORICAL_CANDLE_QUOTE_SCREEN_NOT_REALIZED_PNL",
        "candles_parsed": all_rows, "multi_strike_groups": unique_groups,
        "aligned_price_pair_checks": checks,
        "missing_pair_checks": missing,
        "gross_positive_player_time_samples": len(candidates),
        "illustratively_fee_positive_samples": sum(
            row["positive_after_standard_fees"] for row in candidates
        ),
        "apparent_episodes": len(episodes),
        "realized_profit_usd": None,
        "realistic_two_leg_fill_rate": None,
        "contract_rules_verified": False,
        "historical_orderbook_depth_verified": False,
        "warning": "Historical OHLC candle closes are neither synchronous live quotes nor confirmed fills; special fees and void/scalar settlement may differ.",
        "candidates": candidates[:200],
        "episodes": episodes[:200],
    }


def read_jsonl(path):
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", default="data/historical")
    p.add_argument("--output", default="outputs/historical_backtest.json")
    p.add_argument("--contracts", type=int, default=1)
    args = p.parse_args()
    src = Path(args.input)
    manifest_path = src / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    if manifest.get("candles", 0) < 1:
        raise RuntimeError("No genuine historical candles; refusal to report zero opportunities")
    markets = read_jsonl(src / "markets.jsonl")
    quotes = read_jsonl(src / "quotes.jsonl")
    result = study(markets, quotes, args.contracts, manifest.get("interval_minutes", 60))
    result["source_manifest"] = manifest
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items()
                      if k not in ("candidates", "episodes", "source_manifest")}, indent=2))
    print("EVIDENCE_FILE:", out)


if __name__ == "__main__":
    main()
