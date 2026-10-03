"""writer.py - AI-written 'Market brief' and 'Shipping watch' -> data/articles.json.
Facts come only from collected headlines and PortWatch numbers. Needs ANTHROPIC_API_KEY."""
import json, os, re, sys
from datetime import datetime, timezone, timedelta

MODEL = os.environ.get("WRITER_MODEL", "claude-haiku-4-5-20251001")
RULES = ("Write only from the material below. Do not invent numbers, quotes, names or events. "
         "No buy/sell/hold advice, price targets or recommendations on any security. Neutral, plain English. "
         "Format: first line is the headline (max 12 words, no quotes or markdown), then a blank line, then 3-4 short "
         "paragraphs separated by blank lines, then a final paragraph starting 'Watch:' with 2-3 things to watch. "
         "Total 250-330 words. Name sources where useful.")


def jload(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def pick(events, hours=36, n=12, now=None):
    now = now or datetime.now(timezone.utc)
    cut = (now - timedelta(hours=hours)).isoformat()
    ts = [t for t in events.get("threads", []) if t.get("impact", 0) >= 3 and t.get("updated", "") > cut]
    ts.sort(key=lambda t: (t["impact"], t["updated"]), reverse=True)
    return ts[:n]


def news_lines(threads):
    return "\n".join(f"- [{t['category']}, impact {t['impact']}] {t['items'][0]['title']} "
                     f"({t['items'][0]['source']}). Likely effect: {t.get('effect') or 'n/a'}" for t in threads)


def ship_lines(pw):
    return "\n".join(f"- {k}: {c['avg7_total']} ships/day (7-day avg), {c['avg7_tanker']} tankers/day, "
                     f"{'' if c['change_pct'] is None else str(c['change_pct']) + '% vs prior 90-day avg, '}"
                     f"data to {c['latest_date']}" for k, c in pw.get("chokepoints", {}).items())


def parse_article(text):
    text = re.sub(r"```\w*\n?", "", text).strip()
    title, _, body = text.partition("\n")
    title, body = title.strip().lstrip("# ").strip(), body.strip()
    return (title, body) if title and len(body) > 200 else None


def write(client, kind, task, material):
    r = client.messages.create(model=MODEL, max_tokens=900, messages=[
        {"role": "user", "content": f"{task}\n\n{RULES}\n\nMATERIAL:\n{material}"}])
    return parse_article(r.content[0].text)


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set")
    import anthropic
    client = anthropic.Anthropic()
    events, pw = jload("events.json", {}), jload("data/portwatch.json", {})
    threads = pick(events)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    jobs = []
    if threads:
        jobs.append(("Market brief", "Write a morning market brief for Indian investors from these top stories.",
                     news_lines(threads), threads[:8]))
    ship = ship_lines(pw)
    if ship:
        rel = [t for t in threads if t["category"] in ("Conflict", "Crude", "Commodity")][:5]
        jobs.append(("Shipping watch", "Write a short note on what official chokepoint transit counts say about "
                     "oil and trade flows. Use the headlines only for context.",
                     "SHIPPING DATA:\n" + ship + "\n\nRELATED HEADLINES:\n" + news_lines(rel), rel))
    if not jobs:
        print("nothing to write")
        return
    out = jload("data/articles.json", {"articles": []})
    arts = out["articles"]
    for kind, task, material, used in jobs:
        try:
            res = write(client, kind, task, material)
        except Exception as ex:
            print(f"[fail] {kind}: {type(ex).__name__}: {str(ex)[:120]}")
            continue
        if not res:
            print(f"[warn] {kind}: output not usable")
            continue
        aid = f"{today}-{kind.lower().replace(' ', '-')}"
        arts[:] = [a for a in arts if a["id"] != aid]
        arts.insert(0, {"id": aid, "kind": kind, "date": today, "title": res[0], "body": res[1], "model": MODEL,
                        "sources": [{"source": t["items"][0]["source"], "link": t["items"][0]["link"]} for t in used]})
        print(f"wrote {kind}: {res[0]}")
    arts.sort(key=lambda a: a["date"], reverse=True)
    out["articles"] = arts[:14]
    out["updated"] = datetime.now(timezone.utc).isoformat()
    os.makedirs("data", exist_ok=True)
    with open("data/articles.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
