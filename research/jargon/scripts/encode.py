#!/usr/bin/env python3
"""Jargon Encoder — find jargon term from plainspeak description."""
import argparse, json, sys, urllib.request
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent
REGISTRY_PATH = SKILL_DIR / "jargon-registry.json"
MODEL_URL = "http://host.containers.internal:11434/v1/chat/completions"
FAST = "qwen2.5:7b"; HEAVY = "qwen3.6:27b"

def call_llm(messages, heavy=False, max_tokens=100):
    model = HEAVY if heavy else FAST; timeout = 300 if heavy else 15
    payload = json.dumps({"model": model, "messages": messages, "temperature": 0.1, "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(MODEL_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())["choices"][0]["message"]["content"]

def search(desc, terms, theme=None):
    kw = set(desc.lower().split()); matches = []
    for term, entry in terms.items():
        if theme and entry.get("theme", "").lower() != theme.lower(): continue
        all_text = " ".join(entry.get("plainspeak", {}).values()).lower()
        score = sum(1 for k in kw if k in all_text)
        if score > 0: matches.append((score, term))
    matches.sort(key=lambda x: -x[0]); return matches

def main():
    p = argparse.ArgumentParser(); p.add_argument("--description", required=True); p.add_argument("--theme")
    p.add_argument("--top-n", type=int, default=1); p.add_argument("--heavy", action="store_true")
    args = p.parse_args()
    registry = json.load(open(REGISTRY_PATH)) if REGISTRY_PATH.exists() else {"terms": {}}
    matches = search(args.description, registry["terms"], args.theme)
    if matches and matches[0][0] >= 2:
        for s, t in matches[:args.top_n]: print(t)
        return
    ctx = f" in '{args.theme}'" if args.theme else ""
    result = call_llm([{"role": "system", "content": f"Return the jargon term matching this description{ctx}. Just the term. If none, 'NONE'."}, {"role": "user", "content": args.description}], heavy=args.heavy).strip()
    print(result if result != "NONE" else "No match found")

if __name__ == "__main__": main()