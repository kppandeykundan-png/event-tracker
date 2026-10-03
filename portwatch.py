"""portwatch.py - IMF PortWatch daily chokepoint transits -> data/portwatch.json.
No API key. Data is delayed (published weekly). Cite: Sources: UN Global Platform;
IMF PortWatch (portwatch.imf.org). Check IMF terms before commercial use."""
import json, os, statistics, sys, urllib.parse, urllib.request
from datetime import datetime, timezone

BASE = ("https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/"
        "Daily_Chokepoints_Data/FeatureServer/0/query")
WANT = {"Hormuz": "Hormuz", "Bab-el-Mandeb": "Mandeb", "Suez": "Suez", "Malacca": "Malacca"}
DAYS = 400


def query(keyword):
    p = {"where": f"portname LIKE '%{keyword}%'", "outFields": "*",
         "orderByFields": "date DESC", "resultRecordCount": DAYS, "f": "json"}
    req = urllib.request.Request(BASE + "?" + urllib.parse.urlencode(p), headers={"User-Agent": "event-tracker"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def pick(attrs, *needles):
    for k in attrs:
        if all(n in k.lower() for n in needles) and "capacity" not in k.lower():
            return k
    return None


def num(a, key):
    try:
        return int(round(float(a.get(key) or 0))) if key else 0
    except (TypeError, ValueError):
        return 0


def day(v):
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(v / 1000, timezone.utc).strftime("%Y-%m-%d")
    return str(v)[:10]


def parse(features):
    rows = {}
    for f in features:
        a = f.get("attributes", {})
        dk = "date" if "date" in a else pick(a, "date")
        if not dk or a.get(dk) is None:
            continue
        tk = "n_total" if "n_total" in a else pick(a, "n_", "total")
        kk = pick(a, "n_", "tanker")
        rows[day(a[dk])] = {"date": day(a[dk]), "total": num(a, tk), "tanker": num(a, kk)}
    return [rows[d] for d in sorted(rows)]


def summarize(rows):
    if not rows:
        return None
    last7, prior = rows[-7:], rows[-97:-7]
    avg = lambda rs, k: round(statistics.mean(r[k] for r in rs), 1) if rs else None
    base = avg(prior, "total") if len(prior) >= 30 else None
    cur = avg(last7, "total")
    chg = round(100 * (cur / base - 1)) if base else None
    return {"latest_date": rows[-1]["date"], "avg7_total": cur, "avg7_tanker": avg(last7, "tanker"),
            "change_pct": chg, "baseline_total": base, "series": rows[-240:]}


def stress(rows):
    """Per day: how far the last 7 days fall short of the 90 days before them (0-100)."""
    out = []
    for i in range(96, len(rows)):
        base = statistics.mean(r["total"] for r in rows[i - 96:i - 6])
        if base <= 0:
            continue
        cur = statistics.mean(r["total"] for r in rows[i - 6:i + 1])
        out.append((rows[i]["date"], round(100 * max(0.0, min(1.0, 1 - cur / base)), 1)))
    return out


def band(v):
    return "Calm" if v < 10 else "Watchful" if v < 25 else "Strained" if v < 50 else "Severe"


def build_index(allrows):
    per = {k: dict(stress(r)) for k, r in allrows.items()}
    per = {k: v for k, v in per.items() if v}
    if len(per) < 3:
        return None
    series = []
    for d in sorted({d for v in per.values() for d in v}):
        vals = [v[d] for v in per.values() if d in v]
        if len(vals) >= 3:
            series.append({"date": d, "value": round(statistics.mean(vals), 1)})
    if len(series) < 8:
        return None
    latest = series[-1]["value"]
    return {"series": series[-240:], "latest": round(latest), "band": band(latest),
            "change_7d": round(latest - series[-8]["value"]),
            "components": {k: round(v[max(v)]) for k, v in per.items()}}


def main():
    out, shown, allrows = {}, False, {}
    for name, kw in WANT.items():
        try:
            resp = query(kw)
            if "error" in resp:
                raise RuntimeError(str(resp["error"])[:150])
            feats = resp.get("features", [])
            if feats and not shown:
                print("fields:", sorted(feats[0]["attributes"].keys()))
                shown = True
            rows = parse(feats)
            s = summarize(rows)
            if s:
                out[name] = s
                allrows[name] = rows
                print(f"{name}: to {s['latest_date']}, {s['avg7_total']}/day, {s['change_pct']}% vs baseline")
            else:
                print(f"[warn] {name}: no usable rows")
        except Exception as ex:
            print(f"[fail] {name}: {type(ex).__name__}: {ex}")
    if not out:
        sys.exit("PortWatch returned nothing - data/portwatch.json not updated")
    os.makedirs("data", exist_ok=True)
    with open("data/portwatch.json", "w", encoding="utf-8") as f:
        json.dump({"updated": datetime.now(timezone.utc).isoformat(), "chokepoints": out,
                   "index": build_index(allrows)}, f, separators=(",", ":"))


if __name__ == "__main__":
    main()
