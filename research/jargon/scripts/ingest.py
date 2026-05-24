#!/usr/bin/env python3
"""Bulk jargon ingestion — reads text, classifies chunks, updates registry."""
import argparse, json, subprocess, sys
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent

def main():
    p = argparse.ArgumentParser(); p.add_argument("--file"); p.add_argument("--source"); p.add_argument("--source-url")
    p.add_argument("--dry-run", action="store_true"); p.add_argument("--verbose", action="store_true")
    p.add_argument("--heavy", action="store_true"); p.add_argument("--max-chars", type=int, default=5000)
    args = p.parse_args()
    text = open(args.file).read().strip() if args.file else sys.stdin.read().strip()
    if not text: print(json.dumps({"status": "no_input"})); return
    chunks = [text[i:i+args.max_chars] for i in range(0, len(text), args.max_chars)]
    total_new = total_updated = errors = 0; all_terms = []
    for i, chunk in enumerate(chunks):
        print(f"Chunk {i+1}/{len(chunks)} ({len(chunk)} chars)...", file=sys.stderr)
        cmd = ["python3", str(SKILL_DIR / "scripts" / "classify.py")]
        if args.dry_run: cmd.append("--dry-run")
        if args.source: cmd.extend(["--source", args.source])
        if args.source_url: cmd.extend(["--source-url", args.source_url])
        if args.heavy: cmd.append("--heavy")
        try:
            r = subprocess.run(cmd, input=chunk, capture_output=True, text=True, timeout=600 if args.heavy else 180)
            if r.returncode != 0: print(f"ERROR chunk {i+1}: {r.stderr}", file=sys.stderr); errors += 1; continue
            parsed = json.loads(r.stdout)
            total_new += parsed.get("new", 0); total_updated += parsed.get("updated", 0)
            all_terms.extend(parsed.get("jargon_terms", []))
        except Exception as e: print(f"ERROR chunk {i+1}: {e}", file=sys.stderr); errors += 1
    print(json.dumps({"status": "ok" if errors == 0 else "partial", "chunks": len(chunks), "total_new": total_new, "total_updated": total_updated, "total_jargon_found": len(all_terms), "errors": errors, "terms": [{"term": t["term"], "theme": t.get("theme","?"), "source_level": t.get("source_level","?")} for t in all_terms]}, indent=2))

if __name__ == "__main__": main()