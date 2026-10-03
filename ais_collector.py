"""ais_collector.py - burst AIS collector for chokepoints and ports.
Listens a few minutes, merges unique vessels into today's state, writes aggregated
counts to data/ais_daily.json. Env: AISSTREAM_API_KEY (required), MINUTES (default 4),
TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID (optional, for alerts)."""
import asyncio, json, os, sys, time
from datetime import datetime, timezone
import ais_alerts

URL = "wss://stream.aisstream.io/v0/stream"
F_DAILY, F_STATE, F_CACHE = "data/ais_daily.json", "data/state.json", "data/static_cache.json"
KEEP_HISTORY_DAYS, KEEP_CACHE_DAYS = 60, 45


def jload(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def jsave(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(o, f, separators=(",", ":"))


def valid_pos(lat, lon):
    return (lat is not None and lon is not None and abs(lat) <= 90 and abs(lon) <= 180
            and not (lat == 0 and lon == 0))


def area_for(lat, lon, areas):
    for name, a in areas.items():
        s, w, n, e = a["box"]
        if s <= lat <= n and w <= lon <= e:
            return name
    return None


def tanker_class(length, classes):
    if length:
        for c in classes:  # listed largest first
            if length >= c["min_len"]:
                return c["name"]
    return "Unclassified"


def summarize(ids, cache, classes):
    typed = [m for m in ids if m in cache and cache[m][0]]
    tankers = [m for m in typed if 80 <= cache[m][0] <= 89]
    size = {c["name"]: c["barrels_m"] for c in classes}
    by, cap = {}, 0.0
    for m in tankers:
        k = tanker_class(cache[m][1], classes)
        by[k] = by.get(k, 0) + 1
        cap += size.get(k, 0.3)
    return {"vessels": len(ids), "typed_pct": round(100 * len(typed) / len(ids)) if ids else 0,
            "tankers": len(tankers), "classes": by, "capacity_mbbl": round(cap, 1)}


def ingest(m, areas, cache, seen):
    if "error" in m:
        print("[feed error]", str(m["error"])[:160])
        return 0
    meta = m.get("MetaData", {})
    mmsi = str(meta.get("MMSI", ""))
    if not mmsi:
        return 0
    if m.get("MessageType") == "ShipStaticData":
        s = m["Message"]["ShipStaticData"]
        d = s.get("Dimension") or {}
        cache[mmsi] = [s.get("Type") or 0, (d.get("A") or 0) + (d.get("B") or 0),
                       (s.get("Name") or meta.get("ShipName") or "").strip()[:24],
                       int(time.time() // 86400)]
    lat, lon = meta.get("latitude"), meta.get("longitude")
    if valid_pos(lat, lon):
        a = area_for(lat, lon, areas)
        if a:
            seen[a].add(mmsi)
    return 1


async def listen(areas, minutes, cache, seen):
    import websockets
    sub = {"APIKey": os.environ["AISSTREAM_API_KEY"],
           "BoundingBoxes": [[[b[0], b[1]], [b[2], b[3]]] for b in (a["box"] for a in areas.values())],
           "FilterMessageTypes": ["PositionReport", "ShipStaticData"]}
    end, backoff, n = time.time() + minutes * 60, 2, 0
    while time.time() < end:
        try:
            async with websockets.connect(URL, open_timeout=15) as ws:
                await ws.send(json.dumps(sub))  # must be sent within 3 seconds
                backoff = 2
                while time.time() < end:
                    raw = await asyncio.wait_for(ws.recv(), timeout=max(1, end - time.time()))
                    n += ingest(json.loads(raw), areas, cache, seen)
        except asyncio.TimeoutError:
            break
        except Exception as ex:
            print(f"[reconnect] {type(ex).__name__}: {str(ex)[:100]}")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)
    return n


def main():
    if not os.environ.get("AISSTREAM_API_KEY"):
        sys.exit("AISSTREAM_API_KEY is not set")
    cfg, classes = jload("geofences.json", None), jload("tanker_classes.json", [])
    if not cfg:
        sys.exit("geofences.json missing")
    areas = {n: {**a, "kind": k.rstrip("s")} for k in ("chokepoints", "ports") for n, a in cfg.get(k, {}).items()}
    out = jload(F_DAILY, {"areas": {}})
    state, cache = jload(F_STATE, {"date": None, "areas": {}}), jload(F_CACHE, {})
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if state.get("date") and state["date"] != today:  # UTC day rollover: finalise + alert
        for a in out["areas"].values():
            if state["date"] in a["history"]:
                a["history"][state["date"]]["partial"] = False
        ais_alerts.send(ais_alerts.check(out["areas"], state["date"]))
        state = {"date": today, "areas": {}}
    state["date"] = today
    seen = {n: set(state["areas"].get(n, [])) for n in areas}
    n = asyncio.run(listen(areas, float(os.environ.get("MINUTES", "4")), cache, seen))
    print(f"{n} messages")
    if n:
        for name, ids in seen.items():
            state["areas"][name] = sorted(ids)
            a = out["areas"].setdefault(name, {"history": {}})
            a["kind"] = areas[name]["kind"]
            a["history"][today] = {**summarize(ids, cache, classes), "partial": True}
            for d in sorted(a["history"])[:-KEEP_HISTORY_DAYS]:
                del a["history"][d]
            print(f"{name}: {a['history'][today]}")
    else:
        print("[warn] no messages received - history not updated")
    out["updated"] = datetime.now(timezone.utc).isoformat()
    cutoff = int(time.time() // 86400) - KEEP_CACHE_DAYS
    jsave(F_DAILY, out)
    jsave(F_STATE, state)
    jsave(F_CACHE, {m: v for m, v in cache.items() if v[3] >= cutoff})


if __name__ == "__main__":
    main()
