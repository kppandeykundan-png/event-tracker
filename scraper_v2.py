"""scraper_v2.py - RSS -> Claude Haiku classify + cluster into story threads
+ weekly economic calendar -> events.json.  Needs ANTHROPIC_API_KEY."""
import json, os, re, time, hashlib, calendar
from datetime import datetime, timezone, timedelta
import feedparser, requests

MODEL = "claude-haiku-4-5-20251001"
CATS = ["Fed", "RBI", "Conflict", "Crude", "Commodity", "Markets", "Other"]
KEEP_DAYS, MAX_NEW, MAX_ITEMS = 7, 40, 25
CAL_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
CAL_WORDS = re.compile(r"FOMC|Fed|Powell|CPI|NFP|Non-Farm|OPEC|RBI|Repo|Rate Decision|GDP", re.I)
UA = {"User-Agent": "Mozilla/5.0 (event-tracker)"}
now = datetime.now(timezone.utc)


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def fetch_headlines():
    out = {}
    for s in load("sources.json", []):
        name, url = (s.get("name", s.get("url")), s["url"]) if isinstance(s, dict) else (s, s)
        try:
            feed = feedparser.parse(requests.get(url, headers=UA, timeout=20).content)
            if not feed.entries:
                raise ValueError("no entries")
            for e in feed.entries[:30]:
                t = e.get("published_parsed") or e.get("updated_parsed")
                ts = datetime.fromtimestamp(calendar.timegm(t), timezone.utc) if t else now
                title = re.sub(r"\s+", " ", e.get("title", "")).strip()
                if title:
                    hid = hashlib.md5(title.lower().encode()).hexdigest()[:12]
                    out[hid] = {"id": hid, "title": title, "link": e.get("link", ""),
                                "source": name, "time": ts.isoformat()}
        except Exception as ex:
            print(f"[fail] {name}: {ex}")
    print(f"fetched {len(out)} headlines")
    return out


def classify(new, threads):
    """One Claude call: category, market effect, and thread assignment per headline."""
    import anthropic
    client = anthropic.Anthropic()
    recent = [{"id": t["id"], "title": t["title"]} for t in threads[:30]]
    items = [{"n": i, "headline": h["title"]} for i, h in enumerate(new)]
    prompt = (
        f"Categories: {CATS}. Existing story threads: {json.dumps(recent)}\n"
        f"New headlines: {json.dumps(items)}\n\n"
        "For each headline return an object: n, category, effect (one line, max 14 words, the "
        "likely market effect for Indian/global markets), thread (an existing thread id if it is "
        "the same developing story, else \"new\"), thread_title (short, only when thread is "
        "\"new\"). Use category \"Ignore\" for sports, celebrity or irrelevant news. "
        "Headlines about the same new story must share one thread_title. "
        "Reply with a JSON array only, no other text.")
    r = client.messages.create(model=MODEL, max_tokens=4000,
                               messages=[{"role": "user", "content": prompt}])
    text = re.sub(r"```json|```", "", r.content[0].text).strip()
    return json.loads(text)


def fallback_tag(title):
    rules = [("Fed", r"\bfed\b|fomc|powell"), ("RBI", r"\brbi\b|repo rate"),
             ("Conflict", r"war|strike|missile|attack|ceasefire"),
             ("Crude", r"crude|oil|opec|brent"), ("Commodity", r"gold|silver|copper|wheat")]
    for c, p in rules:
        if re.search(p, title, re.I):
            return c
    return "Other"


def build_calendar():
    try:
        rows = requests.get(CAL_URL, headers=UA, timeout=20).json()
    except Exception as ex:
        print(f"[fail] calendar: {ex}")
        return None
    up = []
    for r in rows:
        if r.get("impact") != "High" and not CAL_WORDS.search(r.get("title", "")):
            continue
        try:
            when = datetime.fromisoformat(r["date"]).astimezone(timezone.utc)
        except Exception:
            continue
        if when > now - timedelta(hours=2):
            up.append({"title": r["title"], "country": r.get("country", ""),
                       "impact": r.get("impact", ""), "time": when.isoformat(),
                       "forecast": r.get("forecast", ""), "previous": r.get("previous", "")})
    return sorted(up, key=lambda x: x["time"])[:15]


def main():
    prev = load("events.json", {})
    cache = load("cache.json", {})
    threads = prev.get("threads", [])
    by_id = {t["id"]: t for t in threads}
    headlines = fetch_headlines()
    new = [h for hid, h in headlines.items() if hid not in cache]
    new.sort(key=lambda h: h["time"], reverse=True)
    new = new[:MAX_NEW]
    print(f"{len(new)} new headlines to classify")

    results = []
    if new:
        try:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise RuntimeError("ANTHROPIC_API_KEY not set")
            results = classify(new, threads)
        except Exception as ex:
            print(f"[ai fail] {ex} - using keyword fallback")
            results = [{"n": i, "category": fallback_tag(h["title"]), "effect": "",
                        "thread": "new", "thread_title": h["title"]} for i, h in enumerate(new)]

    new_titles = {}
    for r in results:
        try:
            h = new[int(r["n"])]
        except Exception:
            continue
        cache[h["id"]] = 1
        cat = r.get("category", "Other")
        if cat == "Ignore":
            continue
        item = {**h, "category": cat, "effect": r.get("effect", "")}
        tid = r.get("thread")
        if tid not in by_id:
            key = r.get("thread_title") or h["title"]
            tid = new_titles.get(key) or "t" + hashlib.md5(key.encode()).hexdigest()[:8]
            new_titles[key] = tid
            if tid not in by_id:
                by_id[tid] = {"id": tid, "title": key, "category": cat, "items": []}
                threads.append(by_id[tid])
        by_id[tid]["items"].append(item)

    cutoff = (now - timedelta(days=KEEP_DAYS)).isoformat()
    for t in threads:
        seen = set()
        t["items"] = sorted([i for i in t["items"] if i["id"] not in seen and not seen.add(i["id"])],
                            key=lambda i: i["time"], reverse=True)[:MAX_ITEMS]
        t["updated"] = t["items"][0]["time"] if t["items"] else cutoff
        t["effect"] = next((i["effect"] for i in t["items"] if i["effect"]), "")
    threads = sorted([t for t in threads if t["items"] and t["updated"] > cutoff],
                     key=lambda t: t["updated"], reverse=True)

    cal = build_calendar()
    save("events.json", {"updated": now.isoformat(), "threads": threads,
                         "upcoming": cal if cal is not None else prev.get("upcoming", [])})
    keep = set(headlines) | set(list(cache)[-1500:])
    save("cache.json", {k: 1 for k in cache if k in keep})
    print(f"wrote {len(threads)} threads")


if __name__ == "__main__":
    main()
