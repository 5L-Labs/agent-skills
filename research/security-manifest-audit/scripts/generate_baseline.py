#!/usr/bin/env python3
"""Deterministic Phase-1 evidence baseline for the security-manifest audit.

Reads every skill listed in _run/batches/batch_*.md, extracts static evidence,
and writes security-manifests/<skill>/manifest.yaml + evidence/static.json.
No network, no execution of skill code. LLM reviewers refine shape calls after.
Author: Hermes Agent 01
"""
import json, os, re, glob

REPO = "/opt/data/repos/hermes-audit"
BATCHES = f"{REPO}/security-manifests/_run/batches"
OUT = f"{REPO}/security-manifests"
COMMIT = "88a1c1f4b19d1bc2b9fe8db870dee9ba0803fad5"

TOOLS = [
    "terminal", "file", "web", "browser", "browser_exec", "browser_vault",
    "web_search", "web_extract", "delegate_task", "image_generate", "image_generation",
    "text_to_speech", "vision_analyze", "video_analyze", "video_generate",
    "computer_use", "session_search", "cronjob", "kanban", "memory", "skill_view",
    "skills", "gadget", "ha_call_service", "x_search", "clarify", "process_manage",
    "manage_connections", "browser_use", "tool_search", "tool_call", "write_file",
    "read_file", "search_files", "execute_code",
]
WIDE_TOOLS = {
    "web", "web_search", "web_extract", "browser", "browser_exec", "browser_vault",
    "browser_use", "delegate_task", "image_generate", "image_generation",
    "text_to_speech", "vision_analyze", "video_analyze", "video_generate",
    "computer_use", "x_search", "manage_connections", "tool_search", "tool_call",
}
CLIS = [
    "curl", "wget", "git", "gh", "npm", "npx", "pnpm", "yarn", "pip", "pip3", "uv",
    "python", "python3", "docker", "kubectl", "ssh", "scp", "rsync", "jq", "bash",
    "sh", "zsh", "brew", "apt", "apt-get", "systemctl", "s6-svc", "tmux", "ffmpeg",
    "whois", "dig", "nslookup", "ping", "openssl", "gpg", "aws", "gcloud", "az",
    "hermes", "claude", "codex", "xurl", "himalaya", "gws", "yt-dlp", "pdftotext",
]
CLI_WORDS = {c: re.compile(r"(?<![\w-])" + re.escape(c) + r"(?![\w-])") for c in CLIS}
TOOL_WORDS = {t: re.compile(r"(?<![\w-])" + re.escape(t) + r"(?![\w-])", re.I) for t in TOOLS}
URL_RE = re.compile(r"(?:https?|wss?)://[^\s\"'<>`)\]}]+")
ENV_RE = re.compile(r"(?:os\.(?:environ(?:\.get)?|getenv)|getenv|environ|os\.environ\.get|process\.env|\$\{?|env\[)\s*\(?[\"']?([A-Z][A-Z0-9_]{2,})")
IMPORT_RE = re.compile(r"^\s*(?:from\s+([A-Za-z_][\w.]*)\s+import|import\s+([A-Za-z_][\w.,\s]*))", re.M)


def skills():
    out = []
    for f in sorted(glob.glob(f"{BATCHES}/batch_*.md")):
        for line in open(f, encoding="utf-8", errors="replace"):
            s = line.strip()
            if s.startswith(("optional-skills/", "skills/")):
                out.append(s)
    return sorted(set(out))


def text_files(path):
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules")]
        for fn in sorted(files):
            if fn.endswith((".png", ".jpg", ".jpeg", ".gif", ".pdf", ".ico", ".woff", ".ttf")):
                continue
            fp = os.path.join(root, fn)
            try:
                if os.path.getsize(fp) > 400_000:
                    continue
                yield fp, open(fp, encoding="utf-8", errors="replace").read()
            except OSError:
                continue


def q(s):
    s = str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    return '"' + s + '"'


def ylist(vals, indent="  "):
    if not vals:
        return "[]"
    parts = [""]
    for v in vals:
        parts.append(f"{indent}- {q(v)}")
    return "\n".join(parts)


def ymap_list(vals, indent="    "):
    """List of dicts rendered as YAML block sequence."""
    if not vals:
        return "[]"
    out = [""]
    for d in vals:
        out.append(f"{indent}-")
        first = True
        for k, v in d.items():
            pre = f"{indent}  " if first else f"{indent}  "
            if isinstance(v, list):
                out.append(f"{pre}{k}: {ylist(v, pre + '  ')}")
            else:
                out.append(f"{pre}{k}: {q(v)}")
            first = False
    return "\n".join(out)


def build(path):
    src = os.path.join(REPO, path)
    files = list(text_files(src))
    all_text = "\n".join(t for _, t in files)
    rel = lambda fp: os.path.relpath(fp, src)
    hosts, imports, clis, envs, tools, setup = [], set(), set(), set(), set(), []
    raw_socket = False

    for fp, txt in files:
        r = rel(fp)
        for n, line in enumerate(txt.splitlines(), 1):
            for m in URL_RE.finditer(line):
                url = m.group(0).rstrip(".,;:")
                host = re.sub(r"^[a-z]+://", "", url).split("/")[0].split("@")[-1]
                if host and "." in host:
                    context = line.strip()[:200]
                    if not any(h["host"] == host and h["file"] == r and h["line"] == n for h in hosts):
                        hosts.append({"host": host, "file": r, "line": n, "context": context})
            for m in IMPORT_RE.finditer(line):
                mod = (m.group(1) or m.group(2) or "").split(",")[0].strip().split(".")[0]
                if mod and mod not in ("from", "import"):
                    imports.add(mod)
            for name, rx in CLI_WORDS.items():
                if rx.search(line):
                    clis.add(name)
            for name, rx in TOOL_WORDS.items():
                if rx.search(line):
                    tools.add(name)
            for m in ENV_RE.finditer(line):
                envs.add(m.group(1))
            if re.search(r"whois|:\s*43\b|port\s+43", line, re.I):
                raw_socket = True
            if re.search(r"^\s*(pip(?:3)?\s+install|npm\s+i|npm\s+install|pnpm\s+add|uv\s+pip\s+install|git\s+clone|apt(?:-get)?\s+install|brew\s+install|curl[^\n]*\|\s*(?:ba)?sh|go\s+install|cargo\s+install)\b", line.strip(), re.I):
                setup.append(line.strip()[:200])

    # Drop tool names that only appear as prose in unrelated contexts is left to the LLM reviewer.
    net_hosts = sorted({h["host"] for h in hosts})
    cred_envs = sorted(e for e in envs if re.search(r"KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH|API", e))
    wide = bool(tools & WIDE_TOOLS) or len(net_hosts) > 8 or raw_socket and "whois" in all_text.lower()
    medium = bool(net_hosts or cred_envs or re.search(r"Apple(?:Notes|Reminders)|iMessage|Find My|iCloud|Keychain|IPC", all_text, re.I))
    shape = "wide" if wide else ("medium" if medium else "narrow")

    tool_reach = []
    for t in sorted(tools):
        tool_reach.append((t, "wide" if t in WIDE_TOOLS else ("medium" if t in ("terminal", "file", "browser_vault") else "narrow")))
    runtime_hosts = []
    for h in net_hosts:
        port = 43 if raw_socket and "whois" in h.lower() else 443
        runtime_hosts.append({"host": h, "ports": [port], "methods": ["GET", "POST"], "why": "static reference in skill files"})
    setup_hosts = [h for h in net_hosts if any(h in s for s in setup)]

    reads = ["workspace"]
    writes = ["workspace"]
    if re.search(r"~/|\$HOME|/home/|\.hermes|\.config", all_text):
        reads.append("home")
    if re.search(r"/etc/|/usr/|/opt/|systemd|launchctl", all_text):
        reads.append("system")
    if re.search(r"<path>|user[- ]specified|USER_PATH|input path", all_text, re.I):
        writes.append("user-specified")

    side = "none"
    if re.search(r"\b(POST|PUT|PATCH|DELETE)\b|git push|gh pr|scp |rsync |upload|publish", all_text, re.I):
        side = "external-write"
    elif net_hosts or tools & WIDE_TOOLS:
        side = "external-read"
    elif re.search(r"write_file|open\(.*['\"]w|mkdir|tee |>>|toml.dump|json.dump", all_text):
        side = "local-write"

    reasoning = (
        f"Deterministic scan of {len(files)} files found {len(net_hosts)} distinct host(s), "
        f"{len(tools)} Hermes tool name(s), {len(setup)} install-time command(s), "
        f"and {len(envs)} environment-variable name(s). "
        + ("Wide signal: open-world tool or many hosts. " if wide else
           "No open-world tool detected; " )
        + ("Medium signal: fixed hosts/credentials/local-app IPC. " if medium and not wide else "")
        + "Shape is a baseline pending per-skill LLM verification of every script and reference."
    )

    static = {
        "hosts_found": hosts,
        "imports": sorted(imports),
        "clis": sorted(clis),
        "env_vars": sorted(envs),
        "hermes_tools": sorted(tools),
        "setup_commands": setup,
        "shape_reasoning": reasoning,
    }
    tools_yaml = "".join(f"  - name: {q(t)}\n    reach: {reach}\n" for t, reach in tool_reach)
    manifest = f"""schema: hermes-security-manifest/v0
skill: {q(os.path.basename(path))}
path: {q(path)}
commit: {q(COMMIT)}
shape: {shape}
summary: {q("Deterministic static baseline; LLM verification pending")}
tools:
{tools_yaml if tools_yaml else "  []"}
resources:
  network:
    runtime: {ymap_list(runtime_hosts, '    ')}
    setup: {ymap_list([{'host': h, 'ports': [443], 'methods': ['GET'], 'why': 'install-time reference'} for h in setup_hosts], '    ')}
    artifact_refs: {ymap_list([{'host': h, 'why': 'URL in skill output'} for h in net_hosts if 'cdn' in h or 'jsdelivr' in h or 'unpkg' in h], '    ')}
    tool_mediated: {ylist(sorted(tools & WIDE_TOOLS), '      ')}
    raw_sockets: {str(raw_socket).lower()}
  disk:
    read: {ylist(reads, '      ')}
    write: {ylist(writes, '      ')}
    est_bytes: small
  hardware:
    gpu: none
    cpu_ram: low
    devices: {ylist([], '      ')}
    platforms: {ylist(['linux', 'macos'], '      ')}
  local_apps: {ylist([], '      ')}
  credentials: {ylist(cred_envs, '      ')}
  out_of_band: {ylist([], '      ')}
side_effects: {side}
delegation: {'inherits-toolsets' if 'delegate_task' in tools else 'none'}
escalations: {ylist([], '  ')}
provenance:
  method: static
  confidence: 0.65
  evidence: {ylist(['evidence/static.json'], '    ')}
  notes: {ylist(['Deterministic baseline generated by generate_baseline.py; verify shape and tool reach against all files before finalising.'], '    ')}
"""
    dest = os.path.join(OUT, path)
    os.makedirs(os.path.join(dest, "evidence"), exist_ok=True)
    with open(os.path.join(dest, "evidence/static.json"), "w", encoding="utf-8") as f:
        json.dump(static, f, indent=2, ensure_ascii=False)
    with open(os.path.join(dest, "manifest.yaml"), "w", encoding="utf-8") as f:
        f.write(manifest)
    return shape


if __name__ == "__main__":
    paths = skills()
    counts = {"narrow": 0, "medium": 0, "wide": 0}
    for i, p in enumerate(paths, 1):
        if not os.path.isdir(os.path.join(REPO, p)):
            print("MISSING SOURCE:", p)
            continue
        counts[build(p)] += 1
        if i % 25 == 0:
            print(f"{i}/{len(paths)} done", flush=True)
    print("skills:", len(paths), "shapes:", counts)
