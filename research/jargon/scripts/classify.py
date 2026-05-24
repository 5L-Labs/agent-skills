#!/usr/bin/env python3
"""
Jargon Classifier — detects, classifies, and stores jargon terms from text.
Uses local Ollama models via /api/generate endpoint.

Usage:
  python3 classify.py --text "DPO is the new SOTA for RLHF alignment"
  python3 classify.py --file /tmp/digest.txt
  python3 classify.py --text "..." --dry-run
  python3 classify.py --text "..." --heavy       # Use slow 27B model
"""

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent
REGISTRY_PATH = SKILL_DIR / "jargon-registry.json"
THEMES_CACHE_PATH = SKILL_DIR / "references" / "themes-cache.json"
OLLAMA_BASE = "http://host.containers.internal:11434"
GENERATE_URL = f"{OLLAMA_BASE}/api/generate"

FAST_MODEL = "qwen2.5:7b"
HEAVY_MODEL = "qwen3.6:27b"
FAST_TIMEOUT = 120
HEAVY_TIMEOUT = 600
FAST_PREDICT = 4000
HEAVY_PREDICT = 8000


def load_registry():
    if REGISTRY_PATH.exists():
        with open(REGISTRY_PATH) as f:
            return json.load(f)
    return {"config": {"version": 1, "default_levels": ["doctor", "lawyer", "high-school", "kindergarten"], "last_theme_refresh": None}, "themes": [], "terms": {}}


def save_registry(registry):
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2)


def load_themes():
    if THEMES_CACHE_PATH.exists():
        with open(THEMES_CACHE_PATH) as f:
            cache = json.load(f)
        cache_date = cache.get("cached_at", "")
        if cache_date and cache_date.startswith(datetime.now(timezone.utc).strftime("%Y-%m-%d")):
            return cache.get("themes", [])
    return []


def call_llm(prompt, heavy=False):
    model_name = HEAVY_MODEL if heavy else FAST_MODEL
    timeout = HEAVY_TIMEOUT if heavy else FAST_TIMEOUT
    num_predict = HEAVY_PREDICT if heavy else FAST_PREDICT
    payload = json.dumps({"model": model_name, "prompt": prompt, "stream": False, "options": {"temperature": 0.1, "num_predict": num_predict, "num_ctx": 8192}}).encode()
    req = urllib.request.Request(GENERATE_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read())
        return result.get("response", "").strip(), result.get("thinking", "")
    except Exception as e:
        print(f"ERROR: LLM call failed: {e}", file=sys.stderr)
        sys.exit(1)


def build_classification_prompt(text, themes, levels):
    themes_str = "\n".join([f"- {t}" for t in themes]) if themes else "(none)"
    levels_str = ", ".join(levels)
    return f"""System: Extract domain-specific jargon terms from text.

Themes:\n{themes_str}

Levels: {levels_str}

For each jargon term, return JSON with: term, theme, source_level, plainspeak (object with 1 key per level).
Skip common tech words (API, GPU, CPU, app, code, data, server, cloud, web, email) and common abbreviations (vs, eg, ie, etc).
Return ONLY: {{"jargon_terms": []}}

Text:
{text[:6000]}

JSON:"""


def parse_response(raw):
    content = raw.strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
    return json.loads(content.strip())


def merge_into_registry(registry, detected, source_info):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    terms = registry["terms"]
    new_c = 0; upd_c = 0
    for dt in detected:
        term = dt["term"]
        if term in terms:
            t = terms[term]; t["last_seen"] = now; t["seen_count"] = t.get("seen_count", 0) + 1
            if source_info and source_info not in [s.get("author") for s in t.get("sources", [])]:
                t.setdefault("sources", []).append(source_info)
            upd_c += 1
        else:
            terms[term] = {"theme": dt.get("theme", "Unclassified"), "sub_theme": dt.get("sub_theme", ""), "source_level": dt.get("source_level", "doctor"), "plainspeak": dt.get("plainspeak", {}), "first_seen": now, "last_seen": now, "seen_count": 1, "sources": [source_info] if source_info else []}
            new_c += 1
    return new_c, upd_c


def main():
    parser = argparse.ArgumentParser(description="Jargon classifier")
    parser.add_argument("--text"); parser.add_argument("--file")
    parser.add_argument("--dry-run", action="store_true"); parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--source"); parser.add_argument("--source-url"); parser.add_argument("--heavy", action="store_true")
    args = parser.parse_args()
    if not args.text and not args.file: text = sys.stdin.read().strip()
    elif args.file: text = open(args.file).read().strip()
    else: text = args.text.strip()
    if not text: print(json.dumps({"jargon_terms": [], "new": 0, "updated": 0})); return
    registry = load_registry(); themes = load_themes()
    levels = registry["config"].get("default_levels", ["doctor", "high-school", "kindergarten"])
    prompt = build_classification_prompt(text, themes, levels)
    raw, thinking = call_llm(prompt, heavy=args.heavy)
    if args.verbose: print(f"THINKING: {thinking[:300]}", file=sys.stderr); print(f"RAW: {raw[:500]}", file=sys.stderr)
    if not raw: print("ERROR: empty response (thinking consumed all tokens)", file=sys.stderr); sys.exit(1)
    try: parsed = parse_response(raw)
    except Exception as e: print(f"ERROR: parse failed: {e}\nRaw: {raw[:500]}", file=sys.stderr); sys.exit(1)
    detected = parsed.get("jargon_terms", [])
    src = None
    if args.source: src = {"author": args.source, "date": datetime.now(timezone.utc).strftime("%Y-%m-%d")}
    if args.source_url and src: src["url"] = args.source_url
    new = updated = 0
    if not args.dry_run: new, updated = merge_into_registry(registry, detected, src); save_registry(registry)
    print(json.dumps({"jargon_terms": detected, "new": new, "updated": updated, "total_terms_in_registry": len(registry["terms"])}, indent=2))


if __name__ == "__main__":
    main()