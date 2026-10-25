"""BTC prediction-market mean-reversion entry with early exit, read-only.

Uses the independent April 2026 Polymarket one-second YES/NO quote archive.
Signal depends ONLY on completed past Binance spot 15m candles.
Entry simulated as 1 contract bought at true best ask 60-90s after opening.
Exit simulated as 1 contract sold at true best bid, requiring >=1 share
displayed size; both entry and exit pay modeled market-taker fees.
Price-driven triggers are conditioned on subsequent snapshots (no lookahead).
If no executable bid before the deadline, report and mark conservatively at
settlement net of entry cost; do not drop no-exit losers from the statistics.
No live accounts or orders.
"""
import csv,io,json,math,statistics,sys
from collections import defaultdict
from pathlib import Path
from btc_multiday_orderbook_backtest import bars,signals,get,BASE,DAYS,STEP,num

STRATEGIES=("combined","two_reverse","z15")
CONFIGS={
 "take_06_stop_08_exit_5m":(.06,.08,5*60),
 "take_08_stop_08_exit_8m":(.08,.08,8*60),
 "take_10_stop_10_exit_10m":(.10,.10,10*60),
 "time_exit_5m":(None,None,5*60),
 "time_exit_10m":(None,None,10*60),
 "time_exit_13m":(None,None,13*60)
}
FEE=lambda p:.07*p*(1-p)
def summary(items):
    if not items:return {"trades":0}
    n=len(items);sum_net=sum(x["net"] for x in items)
    settled=[x for x in items if x["reason"]=="no_bid_settlement_fallback"]
    profits=sum(1 for x in items if x["net"]>0)
    return {
       "trades":n,"profitable_trade_fraction":round(profits/n,5),
       "mean_net_per_share":round(sum_net/n,5),
       "one_share_total_pnl":round(sum_net,5),
       "avg_entry":round(statistics.mean(x["entry"] for x in items),5),
       "avg_exit_if_available":round(statistics.mean(x["exit"] for x in items if x["exit"] is not None),5) if len(settled)<n else None,
       "take_profit_count":sum(x["reason"]=="take_profit" for x in items),
       "stop_loss_count":sum(x["reason"]=="stop_loss" for x in items),
       "time_exit_count":sum(x["reason"]=="time_exit" for x in items),
       "no_bid_settlement_fallback_count":len(settled),
       "gross_profit_per_trade":round(statistics.mean(x["gross"] for x in items),5),
       "mean_roundtrip_taker_fee":round(statistics.mean(x["fees"] for x in items),5),
       "split_early_net":round(sum(x["net"] for x in items if x["day"]<="2026-04-13"),5),
       "split_late_net":round(sum(x["net"] for x in items if x["day"]>="2026-04-14"),5),
       "avg_hold_seconds":round(statistics.mean(x["seconds"] for x in items),1)}
def ingest(states,row,sigmap,day):
    slug=row.get("window_slug","")
    if not slug.startswith("btc-updown-15m-"):return
    try:st=int(slug.rsplit("-",1)[-1])*1000
    except ValueError:return
    sig=sigmap.get(st)
    if not sig:return
    t=num(row,"ts_ms")
    if t is None:return
    state=states.setdefault(slug,{"start":st,"signals":sig,"entries":{},
                                  "outcome":None,"books_seen":0})
    if row.get("outcome") in ("Up","Down"):state["outcome"]=row["outcome"]
    if st+60000<=t<=st+90000:
        for k in STRATEGIES:
            if k in state["entries"]:continue
            sd=sig.get(k)
            if sd not in ("Up","Down"):continue
            prefix="yes" if sd=="Up" else "no"
            a=num(row,prefix+"_ask"); q=num(row,prefix+"_ask_size")
            if a is None or q is None or not .02<=a<=.98 or q<1:continue
            # For each exit regime, simulate an independent one-share position.
            state["entries"][k]={"side":sd,"price":a,"t":int(t),"scenarios":{}}
            for config,params in CONFIGS.items():
                state["entries"][k]["scenarios"][config]={"exit":None,"reason":None,"t_exit":None,
                                                             "deadline":min(st+STEP-10000,int(t)+params[2]*1000)}
    # Need observed later executable bid, not market midpoint or future ask.
    for k,e in state["entries"].items():
        if t<e["t"]+2000:continue
        prefix="yes" if e["side"]=="Up" else "no"
        bid=num(row,prefix+"_bid");size=num(row,prefix+"_bid_size")
        if bid is None or size is None or not 0<bid<1 or size<1:continue
        for config,x in e["scenarios"].items():
            if x["reason"] is not None or t>x["deadline"]:continue
            tp,sl,_=CONFIGS[config]
            change=bid-e["price"]
            if tp is not None and change>=tp-0.0000001:
                x["reason"]="take_profit"
            elif sl is not None and change<=-sl+0.0000001:
                x["reason"]="stop_loss"
            elif t>=x["deadline"]:
                x["reason"]="time_exit"
            if x["reason"]:
                x["exit"]=bid
                x["t_exit"]=int(t)
def main():
    bb=bars();sigmap=signals(bb)
    actual={k:{cfg:[] for cfg in CONFIGS} for k in STRATEGIES}
    seen=0; nentry=0; coverage={}; totalrows=0
    for day in DAYS:
        windows={};lines=0
        with get(BASE+"orderbook_"+day+".csv") as src:
            for row in csv.DictReader(io.TextIOWrapper(src,encoding="utf-8-sig",newline="")):
                lines+=1
                ingest(windows,row,sigmap,day)
        totalrows+=lines
        n_day=0
        for w in windows.values():
            seen+=1
            if w["outcome"] not in ("Up","Down"):continue
            for strat,e in w["entries"].items():
                nentry+=1;n_day+=1
                for config,x in e["scenarios"].items():
                    entry=e["price"];correct=int(w["outcome"]==e["side"])
                    if x["reason"] is None:
                        # This fallback is not a claimed real fill.
                        x["reason"]="no_bid_settlement_fallback"
                        exit_val=correct
                        fees=FEE(entry)
                        duration=900
                    else:
                        exit_val=x["exit"]
                        fees=FEE(entry)+FEE(exit_val)
                        duration=(x["t_exit"]-e["t"])/1000
                    record={
                         "market_start":w["start"],"day":day,
                         "entry":entry,"exit":x["exit"],"reason":x["reason"],
                         "net":exit_val-entry-fees,"gross":exit_val-entry,
                         "fees":fees,"seconds":duration}
                    actual[strat][config].append(record)
        coverage[day]={"rows":lines,"windows":len(windows),"eligible_positions":n_day}
        print("EARLY_EXIT_DAY",day,n_day,flush=True)
    result={
      "source":"Vinayak19112003 pinned 1-second BTC15m Polymarket YES+NO orderbook CSVs",
      "dates":DAYS,"rows":totalrows,"markets_examined":seen,"strategy_entries":nentry,
      "assumptions":"One-share buy at available ask 60-90 seconds into market. Sell at future bid with displayed >=1 share. Both sides incur taker fees 0.07*p*(1-p). Signal only prior completed 15m Binance bars. Stops/targets use observable future bids. Conservative settlement fallback when no executable exit observed.",
      "critical_caveats":"Quote observation is not guaranteed fill. Snapshot timestamps approximate. Buy 1 share may be below exchange minimum. Fees are illustrative, fees based on 2026 schedule not verified per April market. Price spikes, API latency, commissions, and cross-venue settlement discrepancies can change results. Regime and parameter selection require new holdout.",
      "strategies":{s:{c:summary(tr) for c,tr in scenarios.items()} for s,scenarios in actual.items()},
      "daily_coverage":coverage}
    Path("outputs").mkdir(exist_ok=True)
    Path("outputs/btc_mean_reversion_early_exit_26day.json").write_text(json.dumps(result,indent=2))
    print("BTC_EARLY_EXIT_RESULT="+json.dumps({"rows":totalrows,"markets":seen,"entries":nentry,"strategies":result["strategies"]},separators=(",",":")),flush=True)
if __name__=="__main__":main()
