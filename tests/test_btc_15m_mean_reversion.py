"""Read-only Bitcoin 15-minute mean-reversion research.

Run: python -m unittest tests/test_btc_15m_mean_reversion.py -v
Data: Binance public BTCUSDT 15-minute spot candles 2025-01 through 2026-09.
IMPORTANT: Spot movements are a proxy, NOT Polymarket/Chainlink settlement
and NOT historic executable prediction-market prices.
No orders, accounts, or credentials are used.
"""
import calendar
import csv
import io
import json
import math
import statistics
import unittest
import urllib.request
import zipfile
from collections import defaultdict
from datetime import datetime, timezone

INTERVAL_MS = 15 * 60 * 1000
BASE = "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/15m/"
MONTHS = [(y, m) for y in (2025, 2026) for m in range(1, 13)
          if not (y == 2026 and m > 9)]
TEST_START = int(datetime(2026, 7, 1, tzinfo=timezone.utc).timestamp()*1000)
TEST_END = int(datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp()*1000)

def obtain_candles():
    candles = {}
    missing = []
    for year, month in MONTHS:
        filename = f"BTCUSDT-15m-{year}-{month:02d}.zip"
        try:
            req = urllib.request.Request(BASE + filename, headers={"User-Agent": "Mozilla/5.0 quant-research-benchmark"})
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = resp.read()
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                member = next(n for n in zf.namelist() if n.endswith(".csv"))
                with zf.open(member) as f:
                    decoded = io.TextIOWrapper(f, encoding="utf-8")
                    for row in csv.reader(decoded):
                        if len(row) < 5 or not row[0].isdigit():
                            continue
                        ts = int(row[0])
                        if ts > 100_000_000_000_000:
                            ts //= 1000  # Binance spot switched to microseconds in 2025
                        open_, high_, low_, close = map(float, row[1:5])
                        if open_ > 0 and close > 0:
                            candles[ts] = (ts, open_, high_, low_, close)
        except Exception as exc:
            missing.append(f"{year}-{month:02d}: {type(exc).__name__}: {str(exc)[:95]}")
    return sorted(candles.values()), missing

def ci_wilson(wins, count):
    if not count:
        return None
    z = 1.96
    p = wins/count
    den = 1+z*z/count
    center = (p+z*z/(2*count))/den
    radius = z*math.sqrt((p*(1-p)+z*z/(4*count))/count)/den
    return [round(center-radius, 4), round(center+radius, 4)]

def summarize(predictions):
    n = len(predictions)
    wins = sum(int(p == outcome) for _, p, outcome in predictions)
    hit = wins/n if n else None
    out = dict(trades=n, wins=wins, hit_rate=round(hit,6) if n else None,
               wilson_95=ci_wilson(wins, n),
               break_even_max_entry_before_fees=round(hit,6) if n else None)
    # Strictly hypothetical fixed-cost prediction-market purchases.
    for ask, fee in [(0.50,0), (0.50,0.01), (0.53,0.01), (0.55,0.01)]:
        key = f"fixed_{int(ask*100)}c_fee_{int(fee*100)}c_net_per_contract"
        out[key] = round(hit-ask-fee,6) if n else None
    return out

def quant_z(last_16_closes):
    vals = [math.log(x) for x in last_16_closes]
    mean = statistics.mean(vals)
    std = statistics.pstdev(vals)
    return (vals[-1]-mean)/std if std > 0 else 0

def build_cases(candles):
    cases = []
    skipped_gaps = 0
    for idx in range(16, len(candles)):
        segment = candles[idx-16:idx+1]
        if any(segment[j+1][0]-segment[j][0] != INTERVAL_MS for j in range(16)):
            skipped_gaps += 1
            continue
        history = segment[:-1]
        bar = segment[-1]
        dirs = [int(b[4] > b[1]) for b in history[-3:]]
        actual = int(bar[4] > bar[1])
        z = quant_z([b[4] for b in history])
        cases.append(dict(ts=bar[0], actual=actual, last=dirs[-1], past2=dirs[-2:],
                          z=z))
    return cases, skipped_gaps

def signal(case, kind):
    if kind == "reverse_one":
        return 1-case["last"]
    if kind == "reverse_two":
        if case["past2"][0] == case["past2"][1]:
            return 1-case["past2"][-1]
        return None
    if kind == "z2":
        return 0 if case["z"] >= 2 else (1 if case["z"] <= -2 else None)
    if kind == "z15":
        return 0 if case["z"] >= 1.5 else (1 if case["z"] <= -1.5 else None)
    if kind == "two_and_z15":
        a,b = case["past2"]
        if a == b and (case["z"] >= 1.5 and b == 1 or case["z"] <= -1.5 and b == 0):
            return 1-b
        return None
    raise ValueError(kind)

def observed(cases, kind):
    return [(c["ts"], signal(c,kind),c["actual"])
            for c in cases if signal(c,kind) is not None]

def bucket(c):
    d = "".join(str(x) for x in c["past2"])
    z = "hi" if c["z"] > 1.25 else ("lo" if c["z"] < -1.25 else "mid")
    return d + "_" + z

def probability_model(training, testing):
    table = defaultdict(lambda:[0,0])
    for c in training:
        t=table[bucket(c)]
        t[0]+=c["actual"]
        t[1]+=1
    # Shrink the bucket estimate to an uninformative 50% prior,
    # rather than overfitting small samples.
    shrink = 100
    buy_signals = []
    sqerrs = []
    base = []
    for c in testing:
        up,n = table[bucket(c)]
        p = (up+shrink*.5)/(n+shrink)
        y=c["actual"]
        sqerrs.append((p-y)**2)
        base.append((.5-y)**2)
        if max(p,1-p) > .55:
            buy_signals.append((c["ts"],int(p>.5),y))
    return {"train_rows":len(training), "test_rows":len(testing),
            "bucket_estimates":{k:{"observations":v[1],"p_up":round((v[0]+50)/(v[1]+100),5)} for k,v in sorted(table.items())},
            "brier":round(statistics.mean(sqerrs),6),
            "baseline_brier":round(statistics.mean(base),6),
            "selected_over_55pct":summarize(buy_signals)}

class BitcoinMeanReversionStudy(unittest.TestCase):
    def test_historical_15m_backtest(self):
        candles, missing = obtain_candles()
        print("BTC_DATA_DOWNLOAD",json.dumps({"candles":len(candles),"missing":missing}),flush=True)
        self.assertFalse(missing, "Historical months missing; partial backtest prohibited")
        self.assertGreater(len(candles), 59000, "Insufficient historical 15-minute candles")
        cases, gap_count = build_cases(candles)
        train = [c for c in cases if c["ts"] < TEST_START]
        test = [c for c in cases if TEST_START <= c["ts"] < TEST_END]
        self.assertGreater(len(train), 45000)
        self.assertGreater(len(test), 8000)
        result = {"data_source":"Binance BTCUSDT SPOT OHLCV 15m",
                  "train_before":"2026-07-01T00:00:00Z",
                  "out_of_sample":"2026-07-01 through 2026-09-30 UTC",
                  "spot_candles":len(candles),"train_windows":len(train),
                  "test_windows":len(test),"gap_excluded_windows":gap_count,
                  "strategies":{}}
        for kind in ("reverse_one","reverse_two","z2","z15","two_and_z15"):
            result["strategies"][kind]={"training":summarize(observed(train,kind)),
                                        "test":summarize(observed(test,kind))}
            result["strategies"][kind]["test_by_month"]={}
            for month in (7,8,9):
                monthly = [c for c in test if datetime.fromtimestamp(c["ts"]/1000,timezone.utc).month == month]
                result["strategies"][kind]["test_by_month"][f"2026-{month:02d}"]=summarize(observed(monthly,kind))
        result["conditional_probability_model"] = probability_model(train,test)
        print("BTC_REVERSION_BACKTEST_RESULT="+json.dumps(result,sort_keys=True),flush=True)

if __name__ == "__main__":
    unittest.main()
