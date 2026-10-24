"""Public Kalshi historical data collector. No keys, account access or orders.

Output is raw, auditable JSONL and a manifest; a nonempty manifest is not a
profitability conclusion. Sample bounded by event dates and selected ladders.
"""
import argparse
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = "https://external-api.kalshi.com/trade-api/v2"
SERIES = ("KXNBAPTS", "KXNBAREB", "KXNBAAST", "KXNBA3PT")
USER_AGENT = "standalone-public-arbitrage-research/1.0"


def iso(s):
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError, TypeError):
        return None


def date_from_event(event):
    chunks = str(event).split("-")
    if len(chunks) < 2:
        return None
    try:
        return datetime.strptime(chunks[1][:7], "%y%b%d").date()
    except ValueError:
        return None


def strike(m):
    """Parse only human-readable >= player-stat ladders; refuse unknown types."""
    if m.get("market_type", "binary") != "binary":
        return None
    subtitle = str(m.get("yes_sub_title") or "")
    match = re.fullmatch(r"\s*([\w .'-]{3,80}):\s*(\d+)\+.*", subtitle)
    if not match:
        return None
    try:
        threshold = float(m.get("floor_strike"))
    except (ValueError, TypeError):
        return None
    if threshold != int(match.group(2)) - 0.5:
        return None
    if not m.get("event_ticker") or not m.get("ticker"):
        return None
    return (" ".join(match.group(1).lower().split()), threshold)


def get(path, params):
    if not (path == "/historical/markets"
            or re.fullmatch(r"/historical/markets/[A-Za-z0-9_-]+/candlesticks", path)):
        raise ValueError("Endpoint not allowed; research may only GET public archives")
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                url, method="GET", headers={"User-Agent": USER_AGENT}
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 3:
                raise
        time.sleep(1.5 * (2 ** attempt))
    return None


def enumerate_series(series, earliest, latest, max_pages):
    """Read settled archived market metadata; report pagination completeness."""
    markets = []
    cursor = ""
    complete = False
    seen = set()
    for _ in range(max_pages):
        params = {"series_ticker": series, "limit": 1000}
        if cursor:
            params["cursor"] = cursor
        result = get("/historical/markets", params) or {}
        batch = result.get("markets", [])
        if not isinstance(batch, list):
            raise ValueError("Unexpected market catalog format")
        for market in batch:
            ticker = market.get("ticker")
            if ticker in seen:
                continue
            seen.add(ticker)
            day = date_from_event(market.get("event_ticker"))
            if (day and earliest.date() <= day < latest.date()
                    and market.get("result") in ("yes", "no")
                    and strike(market)):
                markets.append(market)
        cursor = result.get("cursor") or ""
        if not cursor or not batch:
            complete = True
            break
        time.sleep(0.08)
    return markets, {"pages_complete": complete, "markets_matching": len(markets),
                     "pages_capped": not complete}


def choose_groups(catalogs, max_markets):
    """Round-robin all available groups; never select a lone strike."""
    grouped = defaultdict(lambda: defaultdict(list))
    for series, markets in catalogs.items():
        for m in markets:
            player, threshold = strike(m)
            grouped[series][(m["event_ticker"], player)].append((threshold, m))
    eligible = defaultdict(list)
    for series, by_event in grouped.items():
        for (event, player), entries in sorted(by_event.items()):
            strikes = [x[0] for x in entries]
            if len(entries) >= 2 and len(strikes) == len(set(strikes)):
                eligible[series].append((event, player, entries))
    picked = []
    while True:
        progressed = False
        for series in sorted(eligible):
            while eligible[series]:
                _event, _player, entries = eligible[series].pop(0)
                if len(entries) <= max_markets - len(picked):
                    picked.extend((series, m) for _, m in entries)
                    progressed = True
                    break
        if not progressed:
            break
    return picked, sum(len(v) for v in grouped.values())


def fetch(start, end, out, max_markets=100, period=60, max_pages=8):
    if not start < end or max_markets < 2 or period not in (1, 60):
        raise ValueError("Invalid experiment parameters")
    out.mkdir(parents=True, exist_ok=True)
    catalogs = {}
    audit = {}
    for series in SERIES:
        catalogs[series], audit[series] = enumerate_series(
            series, start, end, max_pages
        )
    selected, total_groups = choose_groups(catalogs, max_markets)
    manifest = {
        "source": "public Kalshi historical market and candlestick GET endpoints",
        "from_utc": start.isoformat(), "to_utc_exclusive": end.isoformat(),
        "series": list(SERIES), "interval_minutes": period,
        "catalog": audit, "groups_discovered": total_groups,
        "markets_selected": len(selected), "candles": 0, "errors": [],
        "fully_audited_settlement_rules": False,
        "historical_depth_or_fills": False,
        "sampling_method": "bounded round-robin full player ladders",
        "execution_status": "UNVERIFIED; historical OHLC is not fill data",
    }
    with (out / "markets.jsonl").open("w") as fm, (out / "quotes.jsonl").open("w") as fq:
        for series, market in selected:
            ticker = market["ticker"]
            near = (iso(market.get("occurrence_datetime"))
                    or iso(market.get("close_time")))
            if near is None:
                manifest["errors"].append([ticker, "missing market clock"])
                continue
            left = max(start, near - timedelta(hours=12))
            right = min(end, near)
            if left >= right:
                continue
            params = {"start_ts": int(left.timestamp()),
                      "end_ts": int(right.timestamp()),
                      "period_interval": period}
            path = ("/historical/markets/"
                    + urllib.parse.quote(ticker, safe="")
                    + "/candlesticks")
            try:
                payload = get(path, params) or {}
                candles = payload.get("candlesticks", [])
                if not isinstance(candles, list):
                    raise ValueError("Missing candlestick list")
                fm.write(json.dumps({"series": series, "ticker": ticker,
                                      "market": market}) + "\n")
                for candle in candles:
                    fq.write(json.dumps({"ticker": ticker, "series": series,
                                         "candle": candle}) + "\n")
                manifest["candles"] += len(candles)
                time.sleep(0.06)
            except (OSError, ValueError, KeyError) as exc:
                manifest["errors"].append([ticker, type(exc).__name__])
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    if manifest["markets_selected"] == 0 or manifest["candles"] == 0:
        raise RuntimeError("No usable historical candles retrieved; not a zero-edge result")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2026-01-01")
    parser.add_argument("--end", default="2026-02-01")
    parser.add_argument("--max-markets", type=int, default=100)
    parser.add_argument("--period", type=int, default=60, choices=[1, 60])
    parser.add_argument("--max-pages", type=int, default=8)
    parser.add_argument("--out", default="data/historical")
    args = parser.parse_args()
    start = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    fetch(start, end, Path(args.out), args.max_markets, args.period, args.max_pages)


if __name__ == "__main__":
    main()
