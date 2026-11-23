#!/usr/bin/env python3
"""Format WaytoAGI daily full-content JSON into a phone-width Signal digest (plain text)."""
import json, re, sys

SRC = "/opt/data/cache/waytoagi/wt_daily_full.json"
OUT = "/opt/data/cache/scratch/wt_digest.txt"
MAX = 1500

BOILER = re.compile(r"^[📌🔗ㅤ\s]*(this article is a (repost|reprint)|本文为(转载|转发)).*$", re.I)
MARKER = re.compile(r"^[\U0001F300-\U0001FAFF\u200B\uFEFFㅤ]+\s*")


def fix_links(text: str) -> str:
    def repl(m):
        label, url = m.group(1).strip(), m.group(2).strip()
        if not label or label == url or "..." in label or label.lower().startswith("h["):
            return url
        return f"{label} ({url})"
    text = re.sub(r"\[([^\]]*)\]\((https?://[^)\s]+)\)", repl, text)
    # repair mangled "h[ttps://...](url)" leftovers
    text = re.sub(r"h\s*\[[^\]]*\]\((https?://[^)\s]+)\)", r"\1", text)
    text = text.replace("hhttp", "http")
    return text


def clean(body: str) -> str:
    body = fix_links(body)
    lines = []
    for ln in body.split("\n"):
        ln = ln.rstrip()
        ln = ln.replace("ㅤ", "").strip()
        if not ln:
            continue
        if BOILER.match(ln):
            continue
        ln = MARKER.sub("", ln).strip()
        ln = re.sub(r"^Original [Ll]ink:\s*", "Original link: ", ln)
        if ln:
            lines.append(ln)
    return "\n".join(lines)


def main():
    d = json.load(open(SRC, encoding="utf-8"))
    items = [i for i in (d.get("items") or []) if i.get("type") != "image"]
    if not items:
        print("daily data not ready", file=sys.stderr)
        return 1
    months = {"1": "Jan", "2": "Feb", "3": "Mar", "4": "Apr", "5": "May", "6": "Jun",
              "7": "Jul", "8": "Aug", "9": "Sep", "10": "Oct", "11": "Nov", "12": "Dec"}

    def fmt_day(day: str) -> str:
        m = re.match(r"(\d+)\s*月\s*(\d+)\s*日", day or "")
        return f"{months.get(m.group(1), m.group(1))} {m.group(2)}" if m else (day or "")

    seen = []
    for i in items:
        d = fmt_day(i.get("day") or "")
        if d and d not in seen:
            seen.append(d)
    span = f"{seen[0]} – {seen[-1]}, 2026" if len(seen) > 1 else (f"{seen[0]}, 2026" if seen else "recent")
    out = [f"WaytoAGI update log — {span} ({len(items)} articles, full English translations)", ""]
    for it in items:
        title = (it.get("title_en") or it.get("title") or "").strip()
        body = clean((it.get("content_en") or "").strip() or (it.get("summary_en") or "").strip())
        if len(body) > MAX:
            cut = body[:MAX]
            body = cut[:cut.rfind("\n")].rstrip() + " [...]"
        out.append(f"• {title}")
        if body:
            out.append(body)
        url = (it.get("url") or "").strip()
        if url:
            out.append(f"Source: {url}")
        out.append("")
    txt = "\n".join(out).strip() + "\n"
    open(OUT, "w", encoding="utf-8").write(txt)
    sys.stdout.write(txt)


if __name__ == "__main__":
    sys.exit(main() or 0)
