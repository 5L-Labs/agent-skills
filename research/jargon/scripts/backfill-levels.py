#!/usr/bin/env python3
"""Backfill — add plainspeak at new sophistication levels for existing terms."""
import argparse, json, sys, urllib.request
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent
REGISTRY_PATH = SKILL_DIR / "jargon-registry.json"
MODEL_URL = "http://host.containers.internal:11434/v1/chat/completions"
FAST = "qwen2.5:7b"; HEAVY = "qwen3.6:27b"

def call_llm(messages, heavy=False):
    model = HEAVY if heavy else FAST; timeout = 300 if heavy else 15
    payload = json.dumps({"model": model, "messages": messages, "temperature": 0.2, "max_tokens": 300}).encode()
    req = urllib.request.Request(MODEL_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp: return json.loads(resp.read())["choices"][0]["message"]["content"]

def main():
    p = argparse.ArgumentParser(); p.add_argument("--term"); p.add_argument("--all", action="store_true")
    p.add_argument("--levels", required=True); p.add_argument("--dry-run", action="store_true"); p.add_argument("--heavy", action="store_true")
    args = p.parse_args()
    if not args.term and not args.all: print("Specify --term or --all", file=sys.stderr); sys.exit(1)
    registry = json.load(open(REGISTRY_PATH)); terms = registry["terms"]; new_levels = [l.strip() for l in args.levels.split(",")]
    targets = list(terms.keys()) if args.all else [args.term]
    if not args.all and args.term not in terms: print(f"'{args.term}' not found", file=sys.stderr); sys.exit(1)
    updated = skipped = 0
    for term in targets:
        e = terms[term]; existing = e.get("plainspeak", {})
        for lv in new_levels:
            if lv in existing: skipped += 1; continue
            if args.dry_run: print(f"[DRY] {term}: would generate '{lv}'", file=sys.stderr); updated += 1; continue
            print(f"{term}: generating '{lv}'...", file=sys.stderr)
            r = call_llm([{"role": "system", "content": f"Define '{term}' ({e.get('theme','?')}) at '{lv}' level in 1-2 sentences."}, {"role": "user", "content": f"Explain {term} at {lv} level."}], heavy=args.heavy)
            if r: existing[lv] = r.strip(); updated += 1
    if not args.dry_run:
        for lv in new_levels:
            if lv not in registry["config"]["default_levels"]: registry["config"]["default_levels"].append(lv)
        json.dump(registry, open(REGISTRY_PATH, "w"), indent=2)
    print(f"Done: {updated} added, {skipped} skipped", file=sys.stderr)

if __name__ == "__main__": main()