#!/usr/bin/env python3
"""Jargon Decoder — translate term to plainspeak at target level."""
import argparse, json, sys, urllib.request
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent
REGISTRY_PATH = SKILL_DIR / "jargon-registry.json"
MODEL_URL = "http://host.containers.internal:11434/v1/chat/completions"
FAST = "qwen2.5:7b"; HEAVY = "qwen3.6:27b"

def call_llm(messages, heavy=False, max_tokens=500):
    model = HEAVY if heavy else FAST; timeout = 300 if heavy else 15
    payload = json.dumps({"model": model, "messages": messages, "temperature": 0.1, "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(MODEL_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())["choices"][0]["message"]["content"]

def main():
    p = argparse.ArgumentParser(); p.add_argument("--term", required=True); p.add_argument("--target-level", default="kindergarten")
    p.add_argument("--heavy", action="store_true"); p.add_argument("--list-levels", action="store_true")
    args = p.parse_args()
    registry = json.load(open(REGISTRY_PATH)) if REGISTRY_PATH.exists() else {"terms": {}}
    terms = registry.get("terms", {}); defaults = registry.get("config", {}).get("default_levels", ["doctor", "lawyer", "high-school", "kindergarten"])
    if args.list_levels:
        if args.term in terms:
            avail = list(terms[args.term].get("plainspeak", {}).keys())
            for lv in defaults: print(f"  {lv:20s} {'✓' if lv in avail else '—'}")
        else: print("Not in registry")
        return
    if args.term in terms:
        ps = terms[args.term].get("plainspeak", {})
        if args.target_level in ps: print(ps[args.target_level]); return
        for lv in defaults:
            if lv in ps: print(ps[lv]); print(f"(Note: '{args.target_level}' not avail; used '{lv}')"); return
        print("No plainspeak available"); return
    print(call_llm([{"role": "system", "content": f"Explain '{args.term}' at {args.target_level} level in 1-2 sentences."}, {"role": "user", "content": f"What does '{args.term}' mean at {args.target_level}?"}], heavy=args.heavy))

if __name__ == "__main__": main()