"""Multi-strategy Bitcoin prediction market research on recorded Polymarket quotes.

26 days, April 2026, public one-second best YES/NO bid+ask snapshots.
One-share hypothetical taker fills, modeled venue fee, no actual fills.
Event-settlement from archive; historical BTCUSDT 15m signals use only completed bars.
Contract fair value is an exploratory proxy using approximate Binance anchor,
NOT the contract's exact Chainlink opening oracle. Treat proxy results as diagnostic only.
"""
import csv,io,json,math,statistics
from collections import defaultdict
from pathlib import Path
from btc_multiday_orderbook_backtest import bars,get,BASE,DAYS,STEP,num

STRATEGIES=[
 "fade_1","fade_2","follow_2","fade_z15","fade_z2","follow_z15","fade_2_z15",
 "rsi_fade","rsi_follow","vol_fade","contract_fade_5c","contract_follow_5c",
 "book_imbalance_follow","book_imbalance_fade","fair_value_gap_5c","fair_value_gap_10c"
]
def prior_feats(klines):
    hist=[b for b in klines if b is not None]
    if len(hist)<96:return {}
    log=[math.log(x[1]) for x in hist]
    rets=[log[i]-log[i-1] for i in range(1,len(log))]
    last2=[hist[-2][1]>hist[-2][0],hist[-1][1]>hist[-1][0]]
    z=(log[-1]-statistics.mean(log[-16:]))/statistics.pstdev(log[-16:]) if statistics.pstdev(log[-16:])>0 else 0
    sigma=statistics.pstdev(rets[-96:])
    gains=[max(r,0) for r in rets[-14:]]
    losses=[max(-r,0) for r in rets[-14:]]
    rsi=100*sum(gains)/(sum(gains)+sum(losses)) if sum(gains)+sum(losses)>0 else 50
    direction="Up" if last2[-1] else "Down"
    reverse="Down" if last2[-1] else "Up"
    sig={"fade_1":reverse,"fade_2":reverse if last2[-1]==last2[-2] else None,
       "follow_2":direction if last2[-1]==last2[-2] else None,
       "fade_z15":"Down" if z>=1.5 else ("Up" if z<=-1.5 else None),
       "fade_z2":"Down" if z>=2 else ("Up" if z<=-2 else None),
       "follow_z15":"Up" if z>=1.5 else ("Down" if z<=-1.5 else None),
       "fade_2_z15":reverse if last2[-1]==last2[-2] and
                            ((last2[-1] and z>=1.5) or (not last2[-1] and z<=-1.5)) else None,
       "rsi_fade":"Up" if rsi<30 else ("Down" if rsi>70 else None),
       "rsi_follow":"Down" if rsi<30 else ("Up" if rsi>70 else None),
       "vol_fade":reverse if abs(rets[-1])>max(.003,2*statistics.pstdev(rets[-96:])) else None}
    return {"signals":sig,"sigma":sigma,"z":z,"rsi":rsi}

def normal_cdf(x):
    return .5*(1+math.erf(x/math.sqrt(2)))
def add_book_signals(st,b,secs):
    # st has first valid observed BTC price near open, not a verified Chainlink strike.
    entry=st["entry"]
    if entry is None:return
    ybid=num(b,"yes_bid");yask=num(b,"yes_ask")
    nbid=num(b,"no_bid");nask=num(b,"no_ask")
    if None in (ybid,yask,nbid,nask) or not(0<ybid<yask<1 and 0<nbid<nask<1):return
    sig=entry["signals"]
    a=st["anchor"]
    # Price movement in the contract from first eligible quote ~0-30s to entry at ~120s.
    if st["first_quote"] is not None:
        diff=(ybid+yask)/2-st["first_quote"]
        sig["contract_fade_5c"]="Down" if diff>=.05 else ("Up" if diff<=-.05 else None)
        sig["contract_follow_5c"]="Up" if diff>=.05 else ("Down" if diff<=-.05 else None)
    ybs=num(b,"yes_bid_size");yas=num(b,"yes_ask_size")
    if ybs is not None and yas is not None and ybs+yas>0:
        imb=ybs/(ybs+yas)
        sig["book_imbalance_follow"]="Up" if imb>=.8 else ("Down" if imb<=.2 else None)
        sig["book_imbalance_fade"]="Down" if imb>=.8 else ("Up" if imb<=.2 else None)
    sig["fair_value_gap_5c"]=None;sig["fair_value_gap_10c"]=None
    spot=num(b,"btc_price")
    sigma=entry.get("sigma")
    if a is not None and spot is not None and a>0 and spot>0 and sigma is not None and sigma>0:
        remaining=(STEP-secs)/STEP
        if remaining>.05:
            fair=normal_cdf(math.log(spot/a)/(sigma*math.sqrt(remaining)))
            edges={"Up":fair-yask,"Down":1-fair-nask}
            for threshold,name in ((.05,"fair_value_gap_5c"),(.10,"fair_value_gap_10c")):
                side=max(edges,key=edges.get)
                sig[name]=side if edges[side]>=threshold else None
    entry["bid"]={"Up":ybid,"Down":nbid}
    entry["ask"]={"Up":yask,"Down":nask}
    entry["depth"]={"Up":num(b,"yes_ask_size"),"Down":num(b,"no_ask_size")}
def numeric_summary(tr):
    if not tr:return {"n":0}
    n=len(tr)
    pnl=[x["net"] for x in tr];wins=sum(x["correct"] for x in tr)
    return {"n":n,"winrate":round(wins/n,4),"correct":wins,
            "entry_mean":round(statistics.mean(x["entry"] for x in tr),4),
            "pnl_per_contract":round(statistics.mean(pnl),5),
            "total_pnl_one_contract_each":round(sum(pnl),4),
            "mean_taker_fees":round(statistics.mean(x["fee"] for x in tr),5)}
def main():
    klines=bars()
    # require enough lookback for 96-bar vol and RSI; load March + April in utility.
    feat={}
    for t in klines:
        hist=[klines.get(t-STEP*i) for i in range(96,0,-1)]
        if all(x is not None for x in hist):
            feat[t]=prior_feats(hist)
    results={s:{"settlement":[],"exit_5m":[],"exit_10m":[]} for s in STRATEGIES}
    day_counts={};fail=0;rows=0;markets=0
    for day in DAYS:
        states={}
        with get(BASE+"orderbook_"+day+".csv") as response:
            for b in csv.DictReader(io.TextIOWrapper(response,encoding="utf-8-sig",newline="")):
                rows+=1
                slug=b.get("window_slug","")
                if not slug.startswith("btc-updown-15m-"):continue
                try:stt=int(slug.rsplit("-",1)[-1])*1000
                except ValueError:continue
                f=feat.get(stt)
                if not f:continue
                tm=num(b,"ts_ms")
                if tm is None:continue
                secs=tm-stt
                st=states.setdefault(slug,{"start":stt,"outcome":None,"anchor":None,"first_quote":None,
                                            "entry":None,"exits":{},"feat":f})
                if b.get("outcome") in ("Up","Down"):st["outcome"]=b["outcome"]
                ybid=num(b,"yes_bid");yask=num(b,"yes_ask")
                if st["anchor"] is None and 0<=secs<30000:
                    st["anchor"]=num(b,"btc_price")
                if st["first_quote"] is None and 0<=secs<45000 and ybid is not None and yask is not None and 0<ybid<yask<1:
                    st["first_quote"]=(ybid+yask)/2
                if st["entry"] is None and 120000<=secs<=150000:
                    yask=num(b,"yes_ask");nask=num(b,"no_ask")
                    ybid=num(b,"yes_bid");nbid=num(b,"no_bid")
                    yas=num(b,"yes_ask_size");nas=num(b,"no_ask_size")
                    if all(q is not None for q in (yask,nask,ybid,nbid,yas,nas)) and all(0<q<1 for q in (yask,nask,ybid,nbid)) and ybid<yask and nbid<nask and yas>=1 and nas>=1:
                        st["entry"]={"t":int(tm),"signals":dict(f["signals"]),"sigma":f["sigma"]}
                        add_book_signals(st,b,secs)
                if st["entry"] is None or tm<=st["entry"]["t"]+2000:continue
                for label,delay in (("exit_5m",300000),("exit_10m",600000)):
                    if label in st["exits"] or tm<st["entry"]["t"]+delay or tm>st["entry"]["t"]+delay+15000:continue
                    by=num(b,"yes_bid");bn=num(b,"no_bid")
                    sy=num(b,"yes_bid_size");sn=num(b,"no_bid_size")
                    if None in (by,bn,sy,sn) or not(0<by<1 and 0<bn<1 and sy>=1 and sn>=1):continue
                    st["exits"][label]={"Up":by,"Down":bn}
        used=0
        for st in states.values():
            if st["entry"] is None or st["outcome"] not in ("Up","Down"):continue
            markets+=1;used+=1
            ent=st["entry"];dirs=ent["signals"]
            for name in STRATEGIES:
                side=dirs.get(name)
                if side not in ("Up","Down"):continue
                price=ent["ask"][side];depth=ent["depth"][side]
                if depth is None or depth<1:continue
                win=int(st["outcome"]==side);cost=.07*price*(1-price)
                results[name]["settlement"].append({"day":day,"correct":win,"entry":price,"fee":cost,"net":win-price-cost})
                for key in ("exit_5m","exit_10m"):
                    sell=st["exits"].get(key,{}).get(side)
                    if sell is None:
                        # Flag omitted exit price, do not drop from denominator;
                        # conservatively fallback to settlement, no claim of execution.
                        net=win-price-cost
                        fee=cost
                    else:
                        fee=cost+.07*sell*(1-sell)
                        net=sell-price-fee
                    results[name][key].append({"day":day,"correct":win,"entry":price,"fee":fee,"net":net,"exit_available":sell is not None})
        day_counts[day]={"market_states":len(states),"complete_entries":used}
        print("SWEEP_POLY_DAY",day,used,flush=True)
    if markets<1000:raise RuntimeError("Insufficient complete Polymarket markets "+str(markets))
    out={"source":"Vinayak19112003 2026-04 independent full YES/NO 1s quote archive, Binance BTC spot",
         "rows":rows,"markets_with_entry_and_outcome":markets,"dates":DAYS,
         "data_limits":"Taker fills at displayed ask, one contract and modeled crypto fee. Late exit unavailable -> settlement outcome fallback. No latency/slippage. BTC oracle anchor APPROXIMATE; fair-value strategies use Binance start price not exact Chainlink oracle. No forward untouched period.",
         "strategies":{},"day_counts":day_counts}
    for strat,grp in results.items():
        out["strategies"][strat]={k:numeric_summary(v) for k,v in grp.items()}
        out["strategies"][strat]["early_half"]=numeric_summary([x for x in grp["settlement"] if x["day"]<="2026-04-13"])
        out["strategies"][strat]["late_half"]=numeric_summary([x for x in grp["settlement"] if x["day"]>="2026-04-14"])
        for key in ("exit_5m","exit_10m"):
            out["strategies"][strat][key]["exit_missing"]=sum(not x["exit_available"] for x in grp[key])
    Path("outputs").mkdir(exist_ok=True)
    Path("outputs/polymarket_btc_full_strategy_sweep.json").write_text(json.dumps(out,indent=2))
    print("POLY_SWEEP_RESULT="+json.dumps({"rows":rows,"markets":markets,"strategies":out["strategies"]},separators=(",",":")),flush=True)
if __name__=="__main__":main()
