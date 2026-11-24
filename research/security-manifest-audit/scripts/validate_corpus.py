#!/usr/bin/env python3
"""Validate a generated security-manifest corpus and print its distribution.

Replaces "a human typed pass into the registry": every check below is
reproducible from the repo, and the JSON result is what belongs in
`change-validation/references/validation-registry.json` (last_result + note).

Checks
  1  coverage        every skill in the audited repo has manifest.yaml + evidence/static.json
  2  yaml/json       both artifacts parse
  3  schema          manifest validates against manifest.v0.json (jsonschema)
  4  stage gate      confidence <= cap(method); static=0.5, +review=0.6,
                     +dynamic=0.75, +eval-backtest=1.0
  5  inputs          provenance.inputs present, so the score is recomputable
  6  secrets         anchored secret patterns absent from manifest and evidence
  7  tools           `file`/`skills`/`web`/`browser`/`process` never listed as tools
  8  hosts           runtime / setup / artifact host sets are disjoint
  9  duplicates      no duplicated hosts within a network list

Usage:
    /usr/bin/python3 validate_corpus.py --corpus /path/to/security-manifests \
        [--schema /path/to/manifest.v0.json] [--repo /path/to/audited-repo] \
        [--json-out result.json] [--report distribution.md]

Exit code is 0 only when every check passes.

Author: Hermes Agent 01
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re
import statistics
import subprocess
import sys

import yaml

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None

STAGE_CAPS = {"static": 0.5, "+review": 0.6, "+dynamic": 0.75, "+eval-backtest": 1.0}
NEVER_TOOLS = {"file", "skills", "skill", "web", "browser", "process", "sandbox"}
SECRET_RES = [
    re.compile(r"(?<![\w-])sk-[A-Za-z0-9]{20,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"gho_[A-Za-z0-9]{36}"),
    re.compile(r"ghs_[A-Za-z0-9]{36}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}"),
]


def corpus_manifests(corpus):
    out = []
    for m in glob.glob(os.path.join(corpus, "**", "manifest.yaml"), recursive=True):
        rel = os.path.relpath(m, corpus)
        if rel.startswith("_run") or rel.startswith("_schema") or rel.startswith("_reports"):
            continue
        out.append(m)
    return sorted(out)


def skills_in_repo(repo):
    paths = []
    for sub in ("skills", "optional-skills"):
        base = os.path.join(repo, sub)
        if os.path.isdir(base):
            for f in glob.glob(os.path.join(base, "**", "SKILL.md"), recursive=True):
                paths.append(os.path.relpath(os.path.dirname(f), repo))
    return sorted(set(paths))


def check_secrets(text):
    for rx in SECRET_RES:
        m = rx.search(text)
        if m:
            return f"{rx.pattern} matched"
    return None


def git_commit(repo):
    try:
        out = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=20)
        sha = out.stdout.strip()
        return sha if re.fullmatch(r"[0-9a-f]{40}", sha) else None
    except Exception:
        return None


def validate(corpus, schema_path, repo):
    failures = []
    manifests = corpus_manifests(corpus)
    schema = None
    if schema_path and os.path.isfile(schema_path):
        schema = json.load(open(schema_path, encoding="utf-8"))
    validator = None
    if schema and jsonschema:
        validator = jsonschema.Draft202012Validator(schema)
    expected_commit = git_commit(repo) if repo else None

    covered = set()
    for m in manifests:
        rel = os.path.relpath(os.path.dirname(m), corpus)
        covered.add(rel)
        skill = os.path.basename(rel)
        try:
            data = yaml.safe_load(open(m, encoding="utf-8"))
        except Exception as exc:
            failures.append((rel, "yaml", f"does not parse: {exc}"))
            continue
        if not isinstance(data, dict):
            failures.append((rel, "yaml", "manifest is not a mapping"))
            continue

        ev_path = os.path.join(os.path.dirname(m), "evidence", "static.json")
        if not os.path.isfile(ev_path):
            failures.append((rel, "coverage", "evidence/static.json missing"))
            evidence = None
        else:
            try:
                evidence = json.load(open(ev_path, encoding="utf-8"))
            except Exception as exc:
                failures.append((rel, "json", f"evidence does not parse: {exc}"))
                evidence = None

        if validator is not None:
            for err in validator.iter_errors(data):
                loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
                failures.append((rel, "schema", f"{loc}: {err.message}"))

        prov = data.get("provenance") or {}
        method = prov.get("method")
        if method not in STAGE_CAPS:
            failures.append((rel, "stage", f"unknown method {method!r}"))
        else:
            raw_conf = prov.get("confidence")
            if raw_conf is None:
                failures.append((rel, "stage", "confidence missing"))
            else:
                try:
                    conf = float(raw_conf)
                except (TypeError, ValueError):
                    failures.append((rel, "stage", "confidence is not a number"))
                else:
                    if conf > STAGE_CAPS[method]:
                        failures.append((rel, "stage",
                                         f"confidence {conf} exceeds cap {STAGE_CAPS[method]} for method {method}"))
        if not prov.get("inputs"):
            failures.append((rel, "inputs", "provenance.inputs missing (score not recomputable)"))

        # the ceiling is what the enforcer proves; a Stage-1 draft must not claim one
        if method == "static" and data.get("ceiling") is not None:
            failures.append((rel, "ceiling",
                             f"ceiling {data.get('ceiling')!r} set at method static "
                             "(unproven; leave null until Stage 4)"))

        # commit must be the audited checkout, not a literal from another run
        if expected_commit and data.get("commit") != expected_commit:
            failures.append((rel, "commit",
                             f"manifest commit {data.get('commit')!r} != repo HEAD {expected_commit}"))

        names = {t.get("name") for t in data.get("tools") or [] if isinstance(t, dict)} - {None}
        bad = names & NEVER_TOOLS
        if bad:
            failures.append((rel, "tools", f"non-tool prose words listed: {sorted(bad)}"))

        net = ((data.get("resources") or {}).get("network") or {})
        rt = [h.get("host") for h in net.get("runtime") or []]
        st = [h.get("host") for h in net.get("setup") or []]
        ar = [h.get("host") for h in net.get("artifact_refs") or []]
        for label, hosts in (("runtime", rt), ("setup", st), ("artifact_refs", ar)):
            dupes = [h for h, c in collections.Counter(hosts).items() if c > 1 and h]
            if dupes:
                failures.append((rel, "duplicates", f"{label} repeats host(s): {sorted(dupes)}"))
        overlap = (set(rt) & set(st)) | (set(rt) & set(ar)) | (set(st) & set(ar))
        if overlap:
            failures.append((rel, "hosts", f"host in more than one list: {sorted(overlap)}"))

        try:
            blob = open(m, encoding="utf-8").read()
            if evidence is not None:
                blob += "\n" + json.dumps(evidence, ensure_ascii=False)
            hit = check_secrets(blob)
            if hit:
                failures.append((rel, "secrets", hit))
        except OSError:
            pass
        del skill

    if repo:
        missing = sorted(set(skills_in_repo(repo)) - covered)
        for rel in missing:
            failures.append((rel, "coverage", "no manifest.yaml for this skill"))
    return manifests, failures


def distribution(manifests, corpus):
    d = {
        "skills": len(manifests),
        "shape": collections.Counter(),
        "shape_by_category": collections.defaultdict(collections.Counter),
        "tool_reach": collections.Counter(),
        "wide_tools": collections.Counter(),
        "runtime_hosts_per_medium": [],
        "top_runtime_hosts": collections.Counter(),
        "top_setup_hosts": collections.Counter(),
        "setup_only_skills": 0,
        "disk_read": collections.Counter(),
        "disk_write": collections.Counter(),
        "est_bytes": collections.Counter(),
        "gpu": collections.Counter(),
        "cpu_ram": collections.Counter(),
        "platforms": collections.Counter(),
        "credentials": collections.Counter(),
        "side_effects": collections.Counter(),
        "delegation": collections.Counter(),
        "raw_sockets": 0,
        "local_apps": collections.Counter(),
        "out_of_band": 0,
        "actions": collections.Counter(),
        "confidence": collections.Counter(),
        "method": collections.Counter(),
    }
    for m in manifests:
        rel = os.path.relpath(os.path.dirname(m), corpus)
        data = yaml.safe_load(open(m, encoding="utf-8")) or {}
        shape = data.get("shape")
        d["shape"][shape] += 1
        parts = rel.split(os.sep)
        category = parts[1] if len(parts) > 2 else "(top-level)"
        d["shape_by_category"][category][shape] += 1
        for t in data.get("tools") or []:
            d["tool_reach"][t.get("reach")] += 1
            if t.get("reach") == "wide":
                d["wide_tools"][t.get("name")] += 1
        net = ((data.get("resources") or {}).get("network") or {})
        rt = net.get("runtime") or []
        if rt:
            d["runtime_hosts_per_medium"].append(len(rt))
        for h in rt:
            d["top_runtime_hosts"][h.get("host")] += 1
        for h in net.get("setup") or []:
            d["top_setup_hosts"][h.get("host")] += 1
        if net.get("setup") and not rt:
            d["setup_only_skills"] += 1
        if net.get("raw_sockets"):
            d["raw_sockets"] += 1
        res = data.get("resources") or {}
        disk = res.get("disk") or {}
        for s in disk.get("read") or []:
            d["disk_read"][s] += 1
        for s in disk.get("write") or []:
            d["disk_write"][s] += 1
        d["est_bytes"][disk.get("est_bytes")] += 1
        hw = res.get("hardware") or {}
        d["gpu"][hw.get("gpu")] += 1
        d["cpu_ram"][hw.get("cpu_ram")] += 1
        for p in hw.get("platforms") or []:
            d["platforms"][p] += 1
        for c in res.get("credentials") or []:
            d["credentials"][c] += 1
        if res.get("local_apps"):
            d["local_apps"][rel] += 1
        if res.get("out_of_band"):
            d["out_of_band"] += 1
        d["side_effects"][data.get("side_effects")] += 1
        deleg = data.get("delegation")
        d["delegation"][deleg.get("inherits") if isinstance(deleg, dict) else deleg] += 1
        for a in data.get("actions") or []:
            d["actions"][a.get("class")] += 1
        prov = data.get("provenance") or {}
        d["confidence"][round(float(prov.get("confidence", 0)), 2)] += 1
        d["method"][prov.get("method")] += 1
    return d


def render_report(d, commit=None):
    out = ["# Security manifest corpus - resource and tool distribution", ""]
    out.append(f"Corpus: {d['skills']} skills"
               + (f", hermes-agent commit {commit}." if commit else "."))
    out.append("Generated deterministically by `scripts/validate_corpus.py`.")
    out.append("")
    sh = d["shape"]
    out.append("## Shape")
    out.append(f"- narrow: {sh['narrow']} | medium: {sh['medium']} | wide: {sh['wide']}")
    out.append("")
    out.append("| category | narrow | medium | wide |")
    out.append("|---|---:|---:|---:|")
    for cat, c in sorted(d["shape_by_category"].items()):
        out.append(f"| {cat} | {c['narrow']} | {c['medium']} | {c['wide']} |")
    out.append("")
    out.append("## Tool reach")
    out.append("- reach counts: " + ", ".join(
        f"{k}={v}" for k, v in sorted(d["tool_reach"].items(), key=lambda x: -x[1])))
    out.append("- tools that make a skill wide: " + (", ".join(
        f"{k}={v}" for k, v in d["wide_tools"].most_common(12)) or "none"))
    out.append("")
    out.append("## Network")
    per = d["runtime_hosts_per_medium"]
    out.append(f"- skills with runtime hosts: {len(per)}")
    if per:
        out.append(f"- runtime hosts per skill: median {statistics.median(per)}, "
                   f"p90 {sorted(per)[int(0.9 * (len(per) - 1))]}, max {max(per)}")
    out.append(f"- setup-only skills (install-time egress, no runtime egress): {d['setup_only_skills']}")
    out.append(f"- raw sockets: {d['raw_sockets']}")
    out.append("- top runtime hosts: " + (", ".join(
        f"{k}={v}" for k, v in d["top_runtime_hosts"].most_common(10)) or "none"))
    out.append("- top setup hosts: " + (", ".join(
        f"{k}={v}" for k, v in d["top_setup_hosts"].most_common(10)) or "none"))
    out.append("")
    out.append("## Disk / hardware")
    out.append("- disk read scopes: " + ", ".join(f"{k}={v}" for k, v in d["disk_read"].most_common()))
    out.append("- disk write scopes: " + ", ".join(f"{k}={v}" for k, v in d["disk_write"].most_common()))
    out.append("- est_bytes: " + ", ".join(f"{k}={v}" for k, v in d["est_bytes"].most_common()))
    out.append("- gpu: " + ", ".join(f"{k}={v}" for k, v in d["gpu"].most_common()))
    out.append("- cpu_ram: " + ", ".join(f"{k}={v}" for k, v in d["cpu_ram"].most_common()))
    out.append("- platforms: " + ", ".join(f"{k}={v}" for k, v in d["platforms"].most_common()))
    out.append("")
    out.append("## Side effects / delegation / gates")
    out.append("- side_effects: " + ", ".join(f"{k}={v}" for k, v in d["side_effects"].most_common()))
    out.append("- delegation: " + ", ".join(f"{k}={v}" for k, v in d["delegation"].most_common()))
    out.append(f"- skills with local-app leaks: {len(d['local_apps'])}")
    out.append(f"- skills with out-of-band gates: {d['out_of_band']}")
    out.append("- credentials declared (names): " + (", ".join(
        f"{k}={v}" for k, v in d["credentials"].most_common(12)) or "none"))
    out.append("")
    out.append("## Provenance")
    out.append("- method: " + ", ".join(f"{k}={v}" for k, v in d["method"].most_common()))
    out.append("- confidence: " + ", ".join(f"{k}={v}" for k, v in sorted(d["confidence"].items())))
    out.append("")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="validate a manifest corpus")
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--schema")
    ap.add_argument("--repo", help="audited repo root; enables the coverage check")
    ap.add_argument("--json-out")
    ap.add_argument("--report", help="write the distribution report here")
    args = ap.parse_args(argv)

    corpus = os.path.abspath(args.corpus)
    schema_path = args.schema or os.path.join(corpus, "_schema", "manifest.v0.json")
    manifests, failures = validate(corpus, schema_path, args.repo)
    dist = distribution(manifests, corpus)
    commit = None
    sample = manifests[0] if manifests else None
    if sample:
        commit = (yaml.safe_load(open(sample, encoding="utf-8")) or {}).get("commit")

    result = {
        "result": "fail" if failures else "pass",
        "corpus": corpus,
        "commit": commit,
        "skills": len(manifests),
        "schema": schema_path if os.path.isfile(schema_path) else None,
        "jsonschema_available": bool(jsonschema),
        "checks": ["coverage", "yaml", "json", "schema", "stage", "inputs",
                   "ceiling", "commit", "secrets", "tools", "hosts", "duplicates"],
        "failures": [{"skill": s, "check": c, "detail": d} for s, c, d in failures],
        "failure_count": len(failures),
        "shape": dict(dist["shape"]),
        "method": {k: v for k, v in dist["method"].items()},
    }
    print(json.dumps(result, indent=2)[:4000])
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    if args.report:
        os.makedirs(os.path.dirname(os.path.abspath(args.report)), exist_ok=True)
        with open(args.report, "w", encoding="utf-8") as fh:
            fh.write(render_report(dist, commit))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
