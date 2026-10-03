"""ais_alerts.py - flag unusual chokepoint/port tanker counts; optional Telegram."""
import json, os, statistics, urllib.parse, urllib.request


def check(areas, date, min_days=5, low=0.6, high=1.5):
    msgs = []
    for name, a in areas.items():
        h = a.get("history", {})
        t = h.get(date)
        if not t or t.get("typed_pct", 0) < 30:
            continue  # too few vessels identified to trust the count
        prev = [v["tankers"] for d, v in sorted(h.items()) if d < date and not v.get("partial")][-14:]
        if len(prev) < min_days:
            continue
        med = statistics.median(prev)
        if med < 5:
            continue
        n = t["tankers"]
        if n < low * med:
            msgs.append(f"{name}: {n} tankers on {date}, down {100*(1-n/med):.0f}% vs 14-day median {med:.0f}")
        elif n > high * med:
            msgs.append(f"{name}: {n} tankers on {date}, up {100*(n/med-1):.0f}% vs 14-day median {med:.0f}")
    return msgs


def send(msgs):
    for m in msgs:
        print("[alert]", m)
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (msgs and tok and chat):
        return
    try:
        body = urllib.parse.urlencode({"chat_id": chat, "text": "AIS alert\n" + "\n".join(msgs)}).encode()
        urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", body, timeout=15)
    except Exception as ex:
        print("[alert send failed]", type(ex).__name__)
