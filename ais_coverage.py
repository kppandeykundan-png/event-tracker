"""ais_coverage.py - where does the free AIS feed actually hear ships?
Subscribes to the whole world for a couple of minutes, counts position reports per
10-degree square, and reports how our own boxes compare. Env: AISSTREAM_API_KEY, MINUTES."""
import asyncio, json, os, sys, time
from collections import Counter, defaultdict
import websockets

URL = "wss://stream.aisstream.io/v0/stream"
MINUTES = float(os.environ.get("MINUTES", "2"))
cells, mmsis = Counter(), defaultdict(set)
total = 0
errors = 0


def cell(lat, lon):
    return (int(lat // 10) * 10, int(lon // 10) * 10)


def handle(raw):
    global total, errors
    m = json.loads(raw)
    if "error" in m:
        errors += 1
        print("[feed error]", str(m["error"])[:160])
        return
    meta = m.get("MetaData", {})
    lat, lon = meta.get("latitude"), meta.get("longitude")
    if lat is None or lon is None or abs(lat) > 90 or abs(lon) > 180:
        return
    total += 1
    c = cell(lat, lon)
    cells[c] += 1
    mmsis[c].add(meta.get("MMSI"))


async def run():
    sub = {"APIKey": os.environ["AISSTREAM_API_KEY"],
           "BoundingBoxes": [[[-90, -180], [90, 180]]],
           "FilterMessageTypes": ["PositionReport"]}
    end, backoff = time.time() + MINUTES * 60, 2
    while time.time() < end:
        try:
            async with websockets.connect(URL, open_timeout=15) as ws:
                await ws.send(json.dumps(sub))
                backoff = 2
                while time.time() < end:
                    handle(await asyncio.wait_for(ws.recv(), timeout=max(1, end - time.time())))
        except asyncio.TimeoutError:
            break
        except Exception as ex:
            print(f"[reconnect] {type(ex).__name__}: {str(ex)[:100]}")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)


def report(secs):
    print("\n" + "=" * 62)
    print(f"WORLD COVERAGE - {secs/60:.1f} min, {total} position reports ({total/secs:.1f}/sec)")
    print("=" * 62)
    print("Busiest 10-degree squares (south-west corner lat/lon : reports, vessels):")
    for (la, lo), n in cells.most_common(15):
        print(f"  lat {la:>4}, lon {lo:>4} : {n:>6} reports, {len(mmsis[(la, lo)]):>4} vessels")
    try:
        cfg = json.load(open("geofences.json", encoding="utf-8"))
    except Exception:
        return
    print("\nSquares holding your areas:")
    for kind in ("chokepoints", "ports"):
        for name, a in cfg.get(kind, {}).items():
            s, w, n, e = a["box"]
            c = cell((s + n) / 2, (w + e) / 2)
            print(f"  {name:24} square lat {c[0]:>4}, lon {c[1]:>4} : {cells.get(c, 0):>6} reports, {len(mmsis.get(c, ())):>4} vessels")
    print("\nREADING IT: thousands of reports worldwide but near-zero in the Gulf/Red Sea/India squares")
    print("= coverage gap in the free feed. Very low totals everywhere = throttling.")


if __name__ == "__main__":
    if not os.environ.get("AISSTREAM_API_KEY"):
        sys.exit("AISSTREAM_API_KEY is not set")
    t0 = time.time()
    try:
        asyncio.run(run())
    finally:
        report(max(1, time.time() - t0))
