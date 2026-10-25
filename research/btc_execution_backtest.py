"""Execution-aware research sample for Polymarket BTC 15-minute markets.

Public archival data: Marketlens June 15 2026 (one UTC day of 96 markets).
Signal inputs: prior *completed* Binance BTCUSDT spot 15m candles.
Cautions: Polymarket settles on a different feed; synthetic NO quotes and
maker trade-through do not demonstrate executable fills or bankroll returns.
No trading account, API credentials, or orders used.
"""
import csv, io, json, math, statistics, urllib.request, zipfile
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

ARCHIVE_SHA = "6eb9b8efda545eddafb2a8f75acb4bcbca6db019"
BASE = ("https://raw.githubusercontent.com/marketlenstrade/polymarket-historical-data/"
        + ARCHIVE_SHA + "/bitcoin-5m-15m-hourly-2026-06-15/")
FEE_RATE = .07
STEP_MS = 15*60*1000
SCORE_KEYS = ("two_streak", "z_1_5", "combined", "calibrated_buckets")
def fetch_bytes(url):
    req = urllib.request.Request(url,headers={"User-Agent":"research/1.0"})
    with urllib.request.urlopen(req,timeout=35) as f:
        return f.read()
def read_csv_url(name):
    return list(csv.DictReader(io.StringIO(fetch_bytes(BASE+name).decode("utf-8-sig"))))
def download_bars():
    out = {}
    for month in ("2026-05","2026-06"):
        data=fetch_bytes("https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/15m/BTCUSDT-15m-"+month+".zip")
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            fn=next(n for n in z.namelist() if n.endswith(".csv"))
            with z.open(fn) as f:
                for x in csv.reader(io.TextIOWrapper(f)):
                    if len(x)<5 or not x[0].isdigit():continue
                    ts=int(x[0]);ts=ts//1000 if ts>10**14 else ts
                    out[ts]={"open":float(x[1]),"close":float(x[4]),"ts":ts}
    return out
def record_signal(c,kind):
    """History c contains precisely the 16 bars before trading decision."""
    last_two=[int(x["close"]>x["open"]) for x in c[-2:]]
    vals=[math.log(x["close"]) for x in c]
    sd=statistics.pstdev(vals);z=(vals[-1]-statistics.mean(vals))/sd if sd else 0.
    streak= last_two[0]==last_two[1]
    side_from_z = ("Down" if z>=1.5 else ("Up" if z<=-1.5 else None))
    if kind=="two_streak":
        return ("Down" if last_two[-1] else "Up") if streak else None
    if kind=="z_1_5":return side_from_z
    if kind=="combined":
        if streak and side_from_z and ((last_two[-1]==1 and side_from_z=="Down") or
                                       (last_two[-1]==0 and side_from_z=="Up")):
            return side_from_z
        return None
    raise ValueError(kind)
def fee(price):return FEE_RATE*price*(1-price)
def summarize(trades):
    if not trades:return {"n":0}
    n=len(trades)
    nwin=sum(x["correct"] for x in trades)
    return {"n":n,"correct":nwin,"accuracy":round(nwin/n,4),
            "avg_entry":round(statistics.mean(x["entry"] for x in trades),4),
            "avg_gross_pnl":round(statistics.mean(x["correct"]-x["entry"] for x in trades),4),
            "avg_net_pnl":round(statistics.mean(x["net"] for x in trades),4),
            "sum_net_one_share":round(sum(x["net"] for x in trades),4),
            "count_positive_net":sum(x["net"]>0 for x in trades)}
def main():
    markets=[m for m in read_csv_url("markets.csv") if m["series"]=="btc-up-or-down-15m"]
    snaps=read_csv_url("snapshots.csv")
    bars=download_bars()
    bymarket=defaultdict(list)
    for s in snaps:bymarket[s["market_id"]].append(s)
    records=[];missing=[]
    for m in sorted(markets,key=lambda z:z["open_time"]):
        t0=int(datetime.fromisoformat(m["open_time"].replace("Z","+00:00")).timestamp()*1000)
        hist=[bars.get(t0-STEP_MS*(i+1)) for i in range(16)][::-1]
        if any(x is None for x in hist):missing.append((m["market_id"],"spot_history_missing"));continue
        ask_candidates=[]
        for s in bymarket[m["market_id"]]:
            lag=int(s["t_ms"])-t0
            try:
                b=float(s["best_bid"]);a=float(s["best_ask"])
            except (ValueError,TypeError):continue
            if 30000<=lag<=180000 and 0<b<a<1:
                ask_candidates.append((int(s["t_ms"]),b,a,s))
        if not ask_candidates:
            missing.append((m["market_id"],"quote_unavailable"));continue
        t,b,a,s=min(ask_candidates,key=lambda x:x[0])
        prevbar=hist[-1]
        spot_prior=(prevbar["close"]>prevbar["open"])
        bar=bars.get(t0)
        spot_actual=("Up" if bar["close"]>bar["open"] else "Down") if bar else None
        record=dict(id=m["market_id"],start=t0,quote_t=t,quote_lag_seconds=(t-t0)/1000,
                    yes_bid=b,yes_ask=a,spread=a-b,
                    outcome=m["winning_outcome"],spot_target=spot_actual,
                    spot_oracle_agree=(spot_actual==m["winning_outcome"]) if spot_actual else None,
                    signals={k:record_signal(hist,k) for k in SCORE_KEYS if k!="calibrated_buckets"})
        records.append(record)
    results={"provenance":{"marketlens_commit":ARCHIVE_SHA,"market_count":len(markets),
            "market_snapshots":len(snaps),"spot_candles":len(bars),
            "fee_assumption":"2026 Polymarket crypto taker fee per share 0.07*p*(1-p), not verified per contract",
            "entry_quote":"first valid published YES book snapshot 30-180 seconds after market open",
            "NO_price":"derived as 1 - YES bid; may not equal executable NO order-book ask"},
            "coverage":{"eligible":len(records),"unavailable":missing,
                "spot_agreement":sum(r["spot_oracle_agree"] is True for r in records),
                "spot_mismatch":sum(r["spot_oracle_agree"] is False for r in records)},
            "taker":{},"maker":{}}
    for k in ("two_streak","z_1_5","combined"):
        for cap in (None,.50,.52,.54,.56,.60):
            tr=[]
            for r in records:
                direction=r["signals"][k]
                if direction is None:continue
                price=r["yes_ask"] if direction=="Up" else 1-r["yes_bid"]
                if cap is not None and price>cap+1e-9:continue
                correct=int(direction==r["outcome"])
                tr.append(dict(correct=correct,entry=price,net=correct-price-fee(price),
                               market_id=r["id"],quote_t=r["quote_t"],side=direction))
            key="any_price" if cap is None else "max_"+str(int(cap*100))+"c"
            results["taker"].setdefault(k,{})[key]=summarize(tr)
    # Maker book-cross estimate only; no proof of fill or queue priority.
    # Real maker trade-through verification requires the per-market trade tape.
    import pandas as pd
    eligible_ids={r["id"] for r in records if r["signals"]["combined"]}
    maker_rows=[]
    for r in records:
        if r["id"] not in eligible_ids:continue
        direction=r["signals"]["combined"]
        spread=r["spread"]
        improv=.01 if spread>=.01999 else 0.
        # YES maker BUY = YES best bid + a tick. NO maker BUY is equivalent
        # to YES SELL at YES ask - a tick; cost is complement.
        p=(r["yes_bid"]+improv) if direction=="Up" else (1-r["yes_ask"]+improv)
        # Never permit crosses or unreasonable book states.
        if not 0<p<1:continue
        yes_limit=p if direction=="Up" else 1-p
        data=fetch_bytes(BASE+"history-"+r["id"]+"-compact.parquet")
        df=pd.read_parquet(io.BytesIO(data),columns=["t","event_type","price","side"])
        d=df[(df["t"]>r["quote_t"]+2000)&(df["t"]<min(r["start"]+15*60*1000,r["quote_t"]+5*60*1000))]
        # Both price and subsequent print required. Some trade prints may be
        # other-token normalized; therefore this is only an indicative proxy.
        trades=d[d["event_type"]=="trade"].copy()
        numeric=pd.to_numeric(trades["price"],errors="coerce")
        if direction=="Up":
            breached=numeric <= yes_limit-.00999
        else:
            breached=numeric >= yes_limit+.00999
        crossed=bool(breached.any())
        maker_rows.append(dict(id=r["id"],direction=direction,quote=p,correct=int(direction==r["outcome"]),
                               through=crossed,subsequent_prints=len(trades),
                               net=(int(direction==r["outcome"])-p) if crossed else 0))
    filled=[dict(entry=x["quote"],correct=x["correct"],net=x["net"]) for x in maker_rows if x["through"]]
    optimistic=[dict(entry=x["quote"],correct=x["correct"],net=x["correct"]-x["quote"]) for x in maker_rows]
    results["maker"]["combined"]={
        "orders":len(maker_rows),"trade_through_indicators":len(filled),
        "trade_through_proxy":summarize(filled),
        "impossible_all_orders_filled_upper_scenario":summarize(optimistic),
        "fill_caveat":"Trade print beyond quote within 5 minutes is NOT evidence our hypothetical order would be filled. No real queue, latency, allocation, or order ID. P&L is scenario only; rebates excluded."}
    Path("outputs").mkdir(exist_ok=True)
    with open("outputs/btc_prediction_execution_one_day.json","w") as f:json.dump(results,f,indent=2)
    print("BTC_EXECUTION_RESEARCH_RESULT="+json.dumps(results,separators=(",",":")),flush=True)
if __name__=="__main__":main()
