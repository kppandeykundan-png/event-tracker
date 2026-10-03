"""macro.py - USD/INR and Brent/WTI crude -> data/macro.json.
USD/INR: ECB reference rate via Frankfurter (free, no key). Crude: US EIA API (free key in EIA_API_KEY;
EIA publishes daily prices in weekly batches). A source that fails is skipped; old data is kept."""
import json, os, urllib.parse, urllib.request
from datetime import date, datetime, timedelta, timezone

UA = {"User-Agent": "event-tracker"}
FX_URLS = ["https://api.frankfurter.app/{start}..?base=USD&symbols=INR",
           "https://api.frankfurter.dev/v1/{start}..?base=USD&symbols=INR"]
EIA = "https://api.eia.gov/v2/petroleum/pri/spt/data/"


def get(url, timeout=30):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return json.load(r)


def pct_change(series, days):
    """% change of the latest value vs the last value on or before (latest date - days)."""
    if len(series) < 2:
        return None
    last = series[-1]
    cut = (date.fromisoformat(last["date"]) - timedelta(days=days)).isoformat()
    prev = [s for s in series if s["date"] <= cut]
    if not prev or not prev[-1]["value"]:
        return None
    return round(100 * (last["value"] / prev[-1]["value"] - 1), 2)


def pack(series):
    if not series:
        return None
    return {"latest": series[-1]["value"], "date": series[-1]["date"], "change_1d_pct": pct_change(series, 1),
            "change_30d_pct": pct_change(series, 30), "series": series[-240:]}


def parse_fx(resp):
    return [{"date": d, "value": round(float(v["INR"]), 4)} for d, v in sorted(resp.get("rates", {}).items()) if "INR" in v]


def parse_eia(resp):
    out = {}
    for r in resp.get("response", {}).get("data", []):
        try:
            v = float(r["value"])
        except (KeyError, TypeError, ValueError):
            continue
        out.setdefault(r.get("series") or r.get("series-id") or "", {})[r["period"]] = v
    return {k: [{"date": d, "value": v} for d, v in sorted(m.items())] for k, m in out.items()}


def fetch_fx():
    start = (date.today() - timedelta(days=250)).isoformat()
    for u in FX_URLS:
        try:
            s = pack(parse_fx(get(u.format(start=start))))
            if s:
                return s
        except Exception as ex:
            print(f"[fx] {type(ex).__name__}: {str(ex)[:100]}")
    return None


def fetch_crude(key):
    q = [("api_key", key), ("frequency", "daily"), ("data[0]", "value"), ("facets[series][]", "RBRTE"),
         ("facets[series][]", "RWTC"), ("sort[0][column]", "period"), ("sort[0][direction]", "desc"), ("length", "600")]
    try:
        s = parse_eia(get(EIA + "?" + urllib.parse.urlencode(q)))
    except Exception as ex:
        print(f"[crude] {type(ex).__name__}: {str(ex)[:100]}")
        return None
    out = {n: pack(s.get(k)) for n, k in (("brent", "RBRTE"), ("wti", "RWTC"))}
    return {k: v for k, v in out.items() if v} or None


def main():
    try:
        prev = json.load(open("data/macro.json", encoding="utf-8"))
    except Exception:
        prev = {}
    fx = fetch_fx() or prev.get("fx")
    key = os.environ.get("EIA_API_KEY")
    crude = (fetch_crude(key) if key else None) or prev.get("crude")
    if not key:
        print("[crude] EIA_API_KEY not set - skipping crude prices")
    os.makedirs("data", exist_ok=True)
    with open("data/macro.json", "w", encoding="utf-8") as f:
        json.dump({"updated": datetime.now(timezone.utc).isoformat(), "fx": fx, "crude": crude}, f, separators=(",", ":"))
    print("fx:", fx and (fx["latest"], fx["date"]), "| crude:", crude and {k: v["latest"] for k, v in crude.items()})


if __name__ == "__main__":
    main()
