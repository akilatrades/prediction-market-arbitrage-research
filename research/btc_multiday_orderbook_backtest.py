"""Read-only BTC 15m Polymarket yes/no execution sample. No orders or credentials.
Source: https://github.com/Vinayak19112003/Polymarket-orderbooks
Independent 1-second snapshots with BOTH tokens, 2026 April 1-26.
Historical quotes are not guarantees of executable fills; maker touch/cross are
scenario proxies, not actual queue-fills. Data attribution: Vinayak19112003.
"""
import csv, io, json, math, statistics, urllib.request, zipfile
from collections import defaultdict
from pathlib import Path
COMMIT="280a29b9b818cc742c096af81c62e4bf899d44dc"
BASE="https://raw.githubusercontent.com/Vinayak19112003/Polymarket-orderbooks/"+COMMIT+"/csv_data/"
DAYS=[f"2026-04-{n:02d}" for n in range(1,27)]
STEP=900000
STRATS=("one_reverse","two_reverse","z15","z2","combined")
def get(url):
    return urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"IndependentResearch/1.0"}),timeout=90)
def bars():
    out={}
    for month in ("2026-03","2026-04"):
        with get("https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/15m/BTCUSDT-15m-"+month+".zip") as f:
            archive=zipfile.ZipFile(io.BytesIO(f.read()))
        with archive.open(next(x for x in archive.namelist() if x.endswith(".csv"))) as f:
            for row in csv.reader(io.TextIOWrapper(f)):
                if len(row)<5 or not row[0].isdigit():continue
                t=int(row[0]);t=t//1000 if t>10**14 else t
                out[t]=(float(row[1]),float(row[4]))
    return out
def signals(b):
    sig={}
    for t in b:
        h=[b.get(t-STEP*i) for i in range(16,0,-1)]
        if any(x is None for x in h):continue
        dirs=[x[1]>x[0] for x in h[-2:]]
        logs=[math.log(x[1]) for x in h]
        std=statistics.pstdev(logs)
        z=(logs[-1]-statistics.mean(logs))/std if std else 0
        streak=dirs[-1]==dirs[-2]
        rev="Down" if dirs[-1] else "Up"
        zside="Down" if z>=1.5 else ("Up" if z<=-1.5 else None)
        sig[t]={"one_reverse":rev,"two_reverse":rev if streak else None,
                "z15":zside,"z2":"Down" if z>=2 else ("Up" if z<=-2 else None),
                "combined":rev if streak and zside==rev else None}
    return sig
def num(row,col):
    try:
        x=float(row.get(col) or "")
        return x if math.isfinite(x) else None
    except (ValueError,TypeError):return None
def ingest(states,row,signal_lookup):
    slug=row.get("window_slug","")
    if not slug.startswith("btc-updown-15m-"):return
    try:start=int(slug.rsplit("-",1)[-1])*1000
    except ValueError:return
    sig=signal_lookup.get(start)
    if not sig:return
    t=num(row,"ts_ms")
    if t is None:return
    state=states.setdefault(slug,{"start":start,"outcomes":set(),"entry":None,
                                  "touch":{},"through":{}})
    if row.get("outcome") in ("Up","Down"):state["outcomes"].add(row["outcome"])
    if state["entry"] is None and start+60000<=t<=start+90000:
        fields=("yes_bid","yes_ask","no_bid","no_ask","yes_ask_size","no_ask_size")
        v={k:num(row,k) for k in fields}
        if all(v[k] is not None and 0<v[k]<1 for k in fields[:4]) and v["yes_bid"]<v["yes_ask"] and v["no_bid"]<v["no_ask"]:
            prices={}
            for side,pfx in (("Up","yes"),("Down","no")):
                bid,ask=v[pfx+"_bid"],v[pfx+"_ask"]
                p=round(bid+(.01 if ask-bid>=.01999 else 0),4)
                if p<ask-.00001:prices[side]=p
            state["entry"]={"t":int(t),"values":v,"signals":sig,"maker_prices":prices}
    e=state["entry"]
    if e is None or not(e["t"]+2000<=t<=min(e["t"]+300000,start+STEP-15000)):return
    for side,p in e["maker_prices"].items():
        ask=num(row,"yes_ask" if side=="Up" else "no_ask")
        if ask is None or not 0<ask<1:continue
        if ask<=p+.00001:state["touch"][side]=True
        if ask<=p-.00999:state["through"][side]=True
def score(t):
    if not t:return {"n":0}
    t=sorted(t,key=lambda x:x["start"])
    wins=sum(x["correct"] for x in t)
    p=[x["correct"]-x["price"]-x["fee"] for x in t]
    running=0;peak=0;maxdd=0
    for x in p:
        running+=x;peak=max(peak,running);maxdd=max(maxdd,peak-running)
    return {"n":len(t),"correct":wins,"accuracy":round(wins/len(t),5),
            "avg_entry":round(statistics.mean(x["price"] for x in t),5),
            "avg_net_per_share":round(statistics.mean(p),5),
            "net_one_share_total":round(sum(p),5),
            "max_sequential_drawdown":round(maxdd,5),
            "ask_depth_ge_10":sum(x.get("depth10",False) for x in t)}
def main():
    b=bars();ss=signals(b);allwin=[];day_counts={};missing=[];rows=0
    for day in DAYS:
        states={}
        try:
            with get(BASE+"orderbook_"+day+".csv") as response:
                for row in csv.DictReader(io.TextIOWrapper(response,encoding="utf-8-sig",newline="")):
                    rows+=1;ingest(states,row,ss)
        except Exception as exc:
            missing.append((day,str(exc)[:100]));continue
        good=[]
        for w in states.values():
            if w["entry"] and len(w["outcomes"])==1:
                w["day"]=day;w["outcome"]=next(iter(w["outcomes"]));good.append(w)
        allwin.extend(good)
        day_counts[day]={"seen":len(states),"valid":len(good)}
        print("DAY_DONE",day,day_counts[day],flush=True)
    if missing:raise RuntimeError("Missing source days: "+repr(missing))
    if len(allwin)<1600:raise RuntimeError("Insufficient usable historical markets: "+str(len(allwin)))
    result={"source":"Vinayak 1-second yes/no top-of-book CSVs; Binance completed 15m bars",
            "source_commit":COMMIT,"dates":DAYS,"rows_seen":rows,
            "windows_usable":len(allwin),"coverage":day_counts,
            "taker_price":"first valid observed top-of-book ask +60 to +90s after open, depth>=1 share",
            "fee":"modeled 0.07*p*(1-p) taker fee per share; no rebates",
            "maker":"rest best bid, improve one tick if spread>=2 ticks; cancel after 5 minutes; crossings are NOT actual fills",
            "key_limitations":"No actual trade execution, latency, queue position or confirmed maker fills. Binance spot signal may not exactly match Chainlink market settlement.",
            "strategies":{}}
    for strategy in STRATS:
        tk=[]; mk_all=[];mk_touch=[];mk_through=[]
        for w in allwin:
            side=w["entry"]["signals"][strategy]
            if side not in ("Up","Down"):continue
            v=w["entry"]["values"];pfx="yes" if side=="Up" else "no"
            ask=v[pfx+"_ask"];depth=v[pfx+"_ask_size"]
            if depth is not None and depth>=1:
                tk.append({"start":w["start"],"price":ask,"correct":int(side==w["outcome"]),
                           "fee":.07*ask*(1-ask),"depth10":depth>=10})
            mp=w["entry"]["maker_prices"].get(side)
            if mp is not None:
                row={"start":w["start"],"price":mp,"correct":int(side==w["outcome"]),"fee":0}
                mk_all.append(row)
                if w["touch"].get(side):mk_touch.append(row)
                if w["through"].get(side):mk_through.append(row)
        result["strategies"][strategy]={
            "taker_any":score(tk),
            "taker_max_50":score([x for x in tk if x["price"]<=.50001]),
            "taker_max_54":score([x for x in tk if x["price"]<=.54001]),
            "taker_max_58":score([x for x in tk if x["price"]<=.58001]),
            "maker_all_fill_unrealistic":score(mk_all),
            "maker_touch_unverified":score(mk_touch),
            "maker_through_unverified":score(mk_through),
            "maker_order_count":len(mk_all)}
    result["combined_half_splits"]={}
    for label,low,high in (("early","2026-04-01","2026-04-13"),("late","2026-04-14","2026-04-26")):
        sample=[]
        for w in allwin:
            if not low<=w["day"]<=high:continue
            side=w["entry"]["signals"]["combined"]
            if not side:continue
            v=w["entry"]["values"];pref="yes" if side=="Up" else "no"
            p=v[pref+"_ask"];size=v[pref+"_ask_size"]
            if size is None or size<1:continue
            sample.append({"start":w["start"],"price":p,"correct":int(w["outcome"]==side),
                           "fee":.07*p*(1-p),"depth10":size>=10})
        result["combined_half_splits"][label]=score(sample)
    Path("outputs").mkdir(exist_ok=True)
    Path("outputs/btc_true_yes_no_multiday_execution.json").write_text(json.dumps(result,indent=2))
    condensed={"rows":rows,"windows":len(allwin),"strategies":{k:{j:v for j,v in entry.items() if j in ("taker_any","taker_max_50","taker_max_54","taker_max_58","maker_through_unverified","maker_touch_unverified","maker_order_count")} for k,entry in result["strategies"].items()},"splits":result["combined_half_splits"]}
    print("BTC_MULTIDAY_EXECUTION_RESULT="+json.dumps(condensed,separators=(",",":")),flush=True)
if __name__=="__main__":main()
