"""build_research.py - index research/*.md (front matter) -> data/research.json."""
import glob, json, os, re


def parse(text):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.S)
    meta = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip().lower()] = v.strip()
    return meta, text[m.end():] if m else text


def main():
    posts = []
    for path in glob.glob("research/*.md"):
        slug = os.path.splitext(os.path.basename(path))[0]
        if slug.startswith("_"):
            continue
        meta, body = parse(open(path, encoding="utf-8").read())
        if meta.get("draft", "").lower() in ("yes", "true", "1") or not meta.get("title"):
            continue
        m = re.match(r"\d{4}-\d{2}-\d{2}", slug)
        summary = meta.get("summary") or re.sub(r"[#*_>\[\]]", "", body).strip().split("\n\n")[0][:200]
        posts.append({"slug": slug, "title": meta["title"], "date": meta.get("date") or (m.group(0) if m else ""),
                      "tickers": [t.strip() for t in meta.get("tickers", "").split(",") if t.strip()],
                      "summary": summary, "pdf": meta.get("pdf", "")})
    posts.sort(key=lambda p: p["date"], reverse=True)
    os.makedirs("data", exist_ok=True)
    with open("data/research.json", "w", encoding="utf-8") as f:
        json.dump({"posts": posts}, f, ensure_ascii=False, separators=(",", ":"))
    print(f"indexed {len(posts)} posts")


if __name__ == "__main__":
    main()
