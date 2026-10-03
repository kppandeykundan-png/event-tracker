"""make_cards.py - share-ready images (1080x1350 PNG) and a caption from data/portwatch.json.
Needs Pillow. Reads site.json (brand) and chart_events.json (event markers)."""
import json, math, os, sys
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
BG, INK, MUTE, SEA, GOLD = (11, 42, 60), (234, 243, 246), (155, 176, 189), (79, 209, 197), (246, 185, 90)
NAMES = {"Hormuz": "Strait of Hormuz", "Bab-el-Mandeb": "Bab-el-Mandeb (Red Sea)",
         "Suez": "Suez Canal", "Malacca": "Strait of Malacca"}
FONT_DIRS = ["/usr/share/fonts/truetype/dejavu/", "/usr/share/fonts/dejavu/", "/Library/Fonts/", "C:/Windows/Fonts/"]


def jload(p, d=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def font(size, bold=False):
    for d in FONT_DIRS:
        for n in (("DejaVuSans-Bold.ttf", "arialbd.ttf") if bold else ("DejaVuSans.ttf", "arial.ttf")):
            try:
                return ImageFont.truetype(d + n, size)
            except OSError:
                pass
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


def fd(s):
    d = datetime.strptime(s, "%Y-%m-%d")
    return f"{d.day} {d.strftime('%b')}"


def nice(m):
    p = 10 ** math.floor(math.log10(m))
    f = m / p
    return (1 if f <= 1 else 2 if f <= 2 else 5 if f <= 5 else 10) * p


def wrap(d, text, f, width):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + [cur] if cur else lines


def draw_chart(img, box, series, vk, base, events):
    x0, y0, x1, y1 = box
    v = [s[vk] for s in series]
    n = len(v)
    top = nice(max(v + [base or 0, 1]))
    X = lambda i: x0 + i * (x1 - x0) / (n - 1)
    Y = lambda y: y1 - y / top * (y1 - y0)
    pts = [(X(i), Y(y)) for i, y in enumerate(v)]
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(ov).polygon(pts + [(x1, y1), (x0, y1)], fill=SEA + (55,))
    img.alpha_composite(ov)
    d = ImageDraw.Draw(img)
    for g in (0, top / 2, top):
        d.line([(x0, Y(g)), (x1, Y(g))], fill=(40, 70, 90), width=2)
        d.text((x0 - 14, Y(g)), f"{g:g}", font=font(24), fill=MUTE, anchor="rm")
    if base:
        x = x0
        while x < x1:
            d.line([(x, Y(base)), (min(x + 14, x1), Y(base))], fill=GOLD, width=3)
            x += 24
        d.text((x1, Y(base) - 8), f"usual {base:.0f}", font=font(24, True), fill=GOLD, anchor="rb")
    for j, e in enumerate(events):
        if series[0]["date"] <= e["date"] <= series[-1]["date"]:
            i = next((k for k, s in enumerate(series) if s["date"] >= e["date"]), n - 1)
            for yy in range(int(y0), int(y1), 12):
                d.line([(X(i), yy), (X(i), yy + 5)], fill=MUTE, width=2)
            right = X(i) > x0 + 0.6 * (x1 - x0)
            d.text((X(i) + (-8 if right else 8), y0 + 4 + (j % 2) * 30), e["label"], font=font(22),
                   fill=INK, anchor="ra" if right else "la")
    d.line(pts, fill=SEA, width=5, joint="curve")
    d.ellipse([pts[-1][0] - 9, pts[-1][1] - 9, pts[-1][0] + 9, pts[-1][1] + 9], fill=SEA)
    d.text((x0, y1 + 14), fd(series[0]["date"]), font=font(24), fill=MUTE, anchor="la")
    d.text((x1, y1 + 14), fd(series[-1]["date"]), font=font(24), fill=MUTE, anchor="ra")


def card(path, brand, headline, big, sub, note, series, vk, base, events, foot):
    img = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(img)
    d.text((90, 90), brand, font=font(34, True), fill=SEA)
    y = 170
    for ln in wrap(d, headline, font(60, True), 900)[:3]:
        d.text((90, y), ln, font=font(60, True), fill=INK)
        y += 76
    d.text((90, 420), big, font=font(150, True), fill=INK)
    d.text((90 + d.textlength(big, font=font(150, True)) + 24, 520), sub, font=font(36), fill=MUTE, anchor="ls")
    for k, ln in enumerate(wrap(d, note, font(30), 900)[:2]):
        d.text((90, 625 + k * 42), ln, font=font(30), fill=INK)
    draw_chart(img, (150, 790, 1000, 1170), series, vk, base, events)
    for k, ln in enumerate(wrap(d, foot, font(24), 900)[:3]):
        d.text((90, 1252 + k * 32), ln, font=font(24), fill=MUTE)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    img.convert("RGB").save(path, optimize=True)


def main():
    pw, site, events = jload("data/portwatch.json"), jload("site.json", {}), jload("chart_events.json", [])
    if not pw:
        sys.exit("data/portwatch.json missing")
    brand, iname = site.get("name", "Market Pulse"), site.get("indexName", "Sea-Lane Stress Index")
    ch = pw["chokepoints"]
    last = max(c["latest_date"] for c in ch.values())
    foot = f"Source: UN Global Platform; IMF PortWatch. Data to {fd(last)}. For information only, not investment advice."
    cards, caps = [], []
    x = pw.get("index")
    if x:
        up = x["change_7d"] >= 0
        note = (f"{'Up' if up else 'Down'} {abs(x['change_7d'])} points in a week. "
                "0 means normal traffic, 100 means empty sea lanes.")
        card("cards/index.png", brand, f"{iname}: {x['band']}", str(x["latest"]), "out of 100",
             note, x["series"], "value", None, events, foot)
        cards.append({"file": "cards/index.png", "label": f"{iname} card"})
        caps.append(f"{iname} today: {x['latest']} out of 100 ({x['band']}). {note}")
    k = max(ch, key=lambda k: abs(ch[k].get("change_pct") or 0))
    c = ch[k]
    if c.get("change_pct") is not None:
        word = "below" if c["change_pct"] < 0 else "above"
        head = f"{NAMES.get(k, k)} traffic is {abs(c['change_pct'])}% {word} usual"
        note = f"{c['avg7_total']} ships a day over the last week, against a usual {round(c.get('baseline_total') or 0)}."
        ev = [e for e in events if not e.get("routes") or k in e["routes"]]
        card("cards/biggest-mover.png", brand, head, str(c["avg7_total"]), "ships a day", note,
             c["series"], "total", c.get("baseline_total"), ev, foot)
        cards.append({"file": "cards/biggest-mover.png", "label": "Biggest mover card"})
        caps.append(f"{head}. {note}")
    with open("cards/caption.txt", "w", encoding="utf-8") as f:
        f.write("\n\n".join(caps) + f"\n\n{foot}\n")
    pw["cards"] = cards
    with open("data/portwatch.json", "w", encoding="utf-8") as f:
        json.dump(pw, f, separators=(",", ":"))
    print("cards:", [c["file"] for c in cards])


if __name__ == "__main__":
    main()
