"""Kalshi BTC 15-minute public historical quote experiment (read-only).

Combines exchange 1-minute historical YES bid/ask candles with prior
COMPLETED Binance BTCUSDT 15m bars. This is a coarse one-minute
quote replay, NOT depth/queue confirmed execution. Simulated buys at asks,
sales at bids; 1-contract Kalshi fees rounded UP per order to 1 cent.
Source: Kalshi historical public API. No API key or orders.
"""
import csv, io, json, math, os, statistics, time, urllib.parse, urllib.request, zipfile
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path

API="https://external-api.kalshi.com/trade-api/v2"
NMARKETS=int(os.environ.get("MAX_KALSHI_MARKETS","320"))
MAX_WORKERS=5

def fetch(url,attempts=4):
    for i in range(attempts):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"IndependentBTCResearch/1.0","Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=25) as resp:return json.load(resp)
        except Exception as e:
            if i==attempts-1:raise
            time.sleep((1.5**i)*.6)
def objnum(v):
    try:
        if v is None:return None
        p=float(v)
        return p if math.isfinite(p) else None
    except (ValueError,TypeError):return None

def candle_num(o,key):
    if not isinstance(o,dict):return None
    return objnum(o.get(key))
def ts(s):
    if s is None:return None
    if isinstance(s,(int,float)):return int(s)
    try:return int(datetime.fromisoformat(s.replace("Z","+00:00")).timestamp())
    except Exception:return None
def fee(p):
    return math.ceil((.07*p*(1-p)-1e-12)*100)/100
def spot():
    result={}
    for month in ("2026-08","2026-09"):
        url="https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/15m/BTCUSDT-15m-"+month+".zip"
        req=urllib.request.Request(url,headers={"User-Agent":"BTCResearch/1.0"})
        with urllib.request.urlopen(req,timeout=25) as res:data=res.read()
        with zipfile.ZipFile(io.BytesIO(data)) as zp:
            nm=next(s for s in zp.namelist() if s.endswith(".csv"))
            with zp.open(nm) as f:
                for row in csv.reader(io.TextIOWrapper(f)):
                    if len(row)<5 or not row[0].isdigit():continue
                    x=int(row[0]); x=x//1000 if x>10**14 else x
                    result[x//1000]=(float(row[1]),float(row[4]))
    return result
def spot_signals(hist):
    dirs=[b[1]>b[0] for b in hist[-2:]]
    log=[math.log(b[1]) for b in hist]
    mean=statistics.mean(log);sd=statistics.pstdev(log)
    z=(log[-1]-mean)/sd if sd else 0
    reverse="no" if dirs[-1] else "yes"
    trend="yes" if dirs[-1] else "no"
    return {"reverse_one":reverse,"reverse_two":reverse if dirs[-1]==dirs[-2] else None,
            "trend_two":trend if dirs[-1]==dirs[-2] else None,
            "zfade_15":("no" if z>=1.5 else ("yes" if z<=-1.5 else None)),
            "zfade_20":("no" if z>=2 else ("yes" if z<=-2 else None)),
            "combined":reverse if dirs[-1]==dirs[-2] and (z>=1.5 if dirs[-1] else z<=-1.5) else None,
            "ztrend_15":("yes" if z>=1.5 else ("no" if z<=-1.5 else None))}
STRATS=("reverse_one","reverse_two","trend_two","zfade_15","zfade_20","combined","ztrend_15",
        "contract_fade","contract_follow")
def pick_markets():
    allm=[]
    for base,params in (
        ("/historical/markets",{"series_ticker":"KXBTC15M","limit":"1000"}),
        ("/markets",{"series_ticker":"KXBTC15M","limit":"1000","status":"settled"})
    ):
        cursor=None
        pages=1 if base.startswith("/historical") else 12
        for page in range(pages):
            q=dict(params)
            if cursor:q["cursor"]=cursor
            try:
                data=fetch(API+base+"?"+urllib.parse.urlencode(q),attempts=3)
                arr=data.get("markets",[])
                allm.extend(arr)
                print("MARKET_CATALOG",base,"page",page+1,"n",len(arr),flush=True)
                cursor=data.get("cursor") or None
                if not cursor or not arr:break
            except Exception as e:
                print("CATALOG_ERROR",base,str(e),flush=True)
                break
    seen=set();f=[]
    for m in allm:
        k=m.get("ticker")
        if k and k not in seen and str(m.get("result","")).lower() in ("yes","no"):
            seen.add(k);f.append(m)
    def mt(m):return ts(m.get("open_time")) or (ts(m.get("close_time")) or 0)-900
    f.sort(key=mt)
    start=ts(os.environ.get("KALSHI_SAMPLE_START","2026-09-01T00:00:00Z"))
    end=ts(os.environ.get("KALSHI_SAMPLE_END","2026-10-01T00:00:00Z"))
    f=[m for m in f if start<=mt(m)<end]
    if len(f)>NMARKETS:
        ix=[int(i*(len(f)-1)/(NMARKETS-1)) for i in range(NMARKETS)]
        f=[f[i] for i in sorted(set(ix))]
    print("CATALOG_SELECTED",len(f),"from",mt(f[0]) if f else 0,"to",mt(f[-1]) if f else 0,flush=True)
    return f

def get_market(m):
    ticker=m["ticker"]
    t0=ts(m.get("open_time")) or ((ts(m.get("close_time")) or 0)-900)
    if not t0: return None
    q=urllib.parse.urlencode({"start_ts":t0,"end_ts":t0+960,"period_interval":1})
    urls=[API+"/historical/markets/"+urllib.parse.quote(ticker)+"/candlesticks?"+q,
          API+"/series/KXBTC15M/markets/"+urllib.parse.quote(ticker)+"/candlesticks?"+q]
    errs=[]
    for url in urls:
        try:
            x=fetch(url,attempts=3)
            bars=x.get("candlesticks",[])
            if bars:return {"meta":m,"t0":t0,"bars":bars}
        except Exception as e:errs.append(str(e)[:100])
    return {"meta":m,"t0":t0,"bars":[],"errors":errs}
def metrics(rows):
    if not rows:return {"n":0}
    n=len(rows);pnl=[r["net"] for r in rows];wins=sum(r["correct"] for r in rows)
    return {"n":n,"correct":wins,"winrate":round(wins/n,4),
            "avg_entry":round(statistics.mean(x["entry"] for x in rows),4),
            "net_per_share":round(statistics.mean(pnl),5),
            "sum_net_one_share":round(sum(pnl),4),
            "positive_net_fraction":round(sum(x>0 for x in pnl)/n,4)}
def main():
    bars=spot();markets=pick_markets()
    if not markets:raise RuntimeError("No matching settled Kalshi markets in Aug-Sep 2026; fail closed.")
    result=[];errors=[]
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs={pool.submit(get_market,m):m for m in markets}
        for i,f in enumerate(as_completed(futs),1):
            try:
                record=f.result()
                if record and record["bars"]:result.append(record)
                else: errors.append({"ticker":futs[f].get("ticker"),"info":record.get("errors",[]) if record else []})
            except Exception as e:
                errors.append({"ticker":futs[f].get("ticker"),"error":str(e)[:150]})
            if i%60==0:print("FETCHED",i,"valid",len(result),"errors",len(errors),flush=True)
    print("KALSHI_SAMPLE",json.dumps({"valid":len(result),"errors":len(errors),"example":result[0] if result else None})[:3500],flush=True)
    if len(result)<40:raise RuntimeError("Insufficient market candles for defensible Kalshi result: "+str(len(result)))
    stats={k:{"settlement":[],"early_exit_8m":[]} for k in STRATS}
    skip={"spot":0,"quotes":0}
    for r in result:
        start=r["t0"];market=r["meta"]
        # Use prior COMPLETED spot candles only. Those ending exactly at the market open are complete.
        hist=[bars.get(start-900*i) for i in range(16,0,-1)]
        if None in hist:
            skip["spot"]+=1;continue
        sig=spot_signals(hist)
        # Prefer the first full 1m candle after t0+120 (avoid using a candle prior to entry).
        series=sorted(r["bars"],key=lambda c:c.get("end_period_ts",0))
        clean=[]
        for c in series:
            bid=candle_num(c.get("yes_bid"),"close")
            ask=candle_num(c.get("yes_ask"),"close")
            end=objnum(c.get("end_period_ts"))
            if bid is not None and ask is not None and end is not None and .01<=bid<ask<=.99:
                clean.append((int(end),bid,ask))
        if not clean:
            skip["quotes"]+=1;continue
        entry=next((c for c in clean if start+180<=c[0]<=start+360),None)
        exit8=next((c for c in clean if start+600<=c[0]<=start+780),None)
        if entry is None:
            skip["quotes"]+=1;continue
        # Contract means subsequent 3 candle mid change is known by entry timestamp only.
        past_mid=[(c[1]+c[2])/2 for c in clean if c[0]<=entry[0]]
        if len(past_mid)>=3:
            delta=past_mid[-1]-past_mid[0]
            if delta>=.06:sig["contract_fade"]="no";sig["contract_follow"]="yes"
            elif delta<=-.06:sig["contract_fade"]="yes";sig["contract_follow"]="no"
            else:sig["contract_fade"]=sig["contract_follow"]=None
        else:sig["contract_fade"]=sig["contract_follow"]=None
        for k,s in sig.items():
            if s is None:continue
            yes=s=="yes";px=entry[2] if yes else 1-entry[1]
            if not .01<px<.99:continue
            win=int(str(market["result"]).lower()==s)
            net=win-px-fee(px)
            stats[k]["settlement"].append({"correct":win,"entry":px,"net":net})
            if exit8 is not None:
                out_px=exit8[1] if yes else 1-exit8[2]
                stats[k]["early_exit_8m"].append({"correct":win,"entry":px,"net":out_px-px-fee(px)-fee(out_px)})
    summary={"source":"Kalshi public 1-minute YES bid and ask historical candles","source_query":"KXBTC15M "+os.environ.get("KALSHI_SAMPLE_START","2026-09-01")+" to "+os.environ.get("KALSHI_SAMPLE_END","2026-10-01"),
        "selected_markets":len(markets),"valid_market_candles":len(result),
        "errors_first_10":errors[:10],"skipped":skip,
        "limitations":"Minute-end quote approximations: there is NO historical depth or precise actual executed ask/bid; NO ask inferred as 1-YES bid; prior Binance spot candle timestamps aligned but exact Kalshi reference differs. Kalshi single-contract fee rounded up 1c. No maker fills validated.",
        "strategies":{k:{j:metrics(rows) for j,rows in v.items()} for k,v in stats.items()}}
    Path("outputs").mkdir(exist_ok=True)
    Path("outputs/kalshi_btc_strategy_sweep.json").write_text(json.dumps(summary,indent=2))
    print("KALSHI_SWEEP_RESULT="+json.dumps(summary,separators=(",",":")),flush=True)
if __name__=="__main__":main()
