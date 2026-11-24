#!/usr/bin/env python3
"""Deterministic static-census baseline for the security-manifest audit (Stage 1).

Scans every skill in the audited repo (any directory containing SKILL.md under
`skills/` or `optional-skills/`), extracts static evidence, and writes
`security-manifests/<skill>/manifest.yaml` + `evidence/static.json`.

Rules encoded here (from review):
- No skill code is executed; no network calls.
- Never emit a value the scan did not observe: ports/methods are empty lists,
  hardware and size defaults are `unknown`, not assumed.
- A URL is a runtime candidate only when it appears in code, a command, or a
  script. URLs in prose or markdown links are documentation. Install-time
  commands land in `setup` only.
- Tool names count only in tool-call contexts, not in prose. `file`, `memory`,
  `skills` and `web` are not tools.
- Redaction: userinfo/query/fragment stripped from every host; no raw source
  text is stored in the evidence.
- Skipped files and directories are recorded in the evidence.
- `method: static` caps confidence at 0.5 and stores the inputs the score will
  be derived from (`provenance.inputs`).

Usage:
    /usr/bin/python3 generate_baseline.py --repo /path/to/audited-repo \
        --out /path/to/audited-repo/security-manifests [--schema schema.json]
Env fallback: HERMES_AUDIT_REPO, HERMES_AUDIT_OUT.

Author: Hermes Agent 01
"""
from __future__ import annotations

import argparse
import ast
import datetime as _dt
import glob
import json
import os
import re
import subprocess
import sys

import yaml

# --- stage caps: confidence can never exceed the cap of the declared method ---
STAGE_CAPS = {"static": 0.5, "+review": 0.6, "+dynamic": 0.75, "+eval-backtest": 1.0}
METHOD = "static"

# ---------------------------------------------------------------------------
# Tool vocabulary.
#
# Which tool NAMES exist is read from the audited repo's `toolsets.py` at the
# audited commit, so a new tool is picked up without editing this file. When
# that file is missing or unparsable the built-in lists below are the fallback.
#
# How WIDE a tool is stays a judgement made here (the repo does not record
# reach): the sets below classify known names, and names discovered only from
# toolsets.py fall back to keyword hints.
#
# `file`, `web`, `skills`, `browser`, `process` and `sandbox` are toolset
# names, not tools. They are dropped outright. Names that are also ordinary
# English words (PROSE_TOOLS) count only in a tool-call context.
# ---------------------------------------------------------------------------
NARROW_TOOLS = {
    "read_file", "write_file", "search_files", "patch", "skill_view", "skill_manage",
    "skills_list", "memory", "clarify", "session_search", "process_manage", "todo_list",
    "cronjob", "kanban", "kanban_create", "kanban_list", "kanban_show",
    "kanban_complete",
}
MEDIUM_TOOLS = {
    "image_generate", "image_generation", "image_gen", "text_to_speech",
    "vision_analyze", "vision", "video_analyze", "video_generate", "ha_call_service",
    "gadget_action", "gadget_display", "gadget_ask", "gadget_play", "gadget_speak",
    "gadget_interpret", "gadget_widget", "gadget_devices", "desktop_preview",
    "desktop_project", "drive_preview", "focus_pane", "read_terminal",
    "read_window_below", "annotate_preview", "set_theme", "show_tip", "gui_tour",
    "close_terminal",
}
# computer_use drives a desktop and whatever that desktop opens: wide.
WIDE_TOOLS = {
    "web_search", "web_extract", "browser_exec", "browser_vault", "browser_use",
    "browser_cdp", "browser_dialog", "browser_navigate", "browser_click",
    "browser_snapshot", "x_search", "manage_connections", "manage_catalog",
    "tool_search", "tool_call", "computer_use",
}
SHELL_TOOLS = {"terminal", "execute_code"}
DELEGATION_TOOLS = {"delegate_task"}
NEVER_TOOLS = {"file", "skills", "skill", "web", "browser", "process", "sandbox"}
PROSE_TOOLS = {
    "terminal", "memory", "patch", "clarify", "kanban", "session_search",
    "computer_use", "vision", "image_gen", "discord", "x_search", "search",
}
WIDE_HINTS = ("search", "browser", "navigate", "click", "snapshot", "extract",
              "fetch", "http", "connect", "catalog", "manage", "web", "computer")
MEDIUM_HINTS = ("image", "video", "speech", "tts", "vision", "camera", "gadget",
                "desktop", "gui", "preview", "theme", "tour", "annotate", "audio",
                "mic", "record", "feishu", "discord", "home")

TOOL_VERB_RE = re.compile(
    r"\b(?:use|uses|using|via|through|call|calls|calling|invoke|invokes|invoking|"
    r"run|runs|running)\s+(?:the\s+)?$", re.I)

# Filled by load_tool_vocabulary() before any scan runs.
ALL_TOOLS: set[str] = set()
AMBIGUOUS: set[str] = set()
TOOL_WORDS: dict[str, re.Pattern] = {}
TOOL_VOCAB_SOURCE = "builtin-fallback"


def classify_reach(name: str) -> str:
    """Reach of a tool this file did not already classify."""
    if name in NARROW_TOOLS:
        return "narrow"
    if name in MEDIUM_TOOLS:
        return "medium"
    if name in WIDE_TOOLS:
        return "wide"
    for hint in WIDE_HINTS:
        if hint in name:
            return "wide"
    for hint in MEDIUM_HINTS:
        if hint in name:
            return "medium"
    return "narrow"


def load_tool_vocabulary(repo: str) -> bool:
    """Read tool names from the audited repo's toolsets.py.

    Tool names are the string elements of list literals; dict keys are toolset
    names and only feed the prose check. Returns True when the repo supplied
    the vocabulary, False when the built-in fallback was used.
    """
    global ALL_TOOLS, AMBIGUOUS, TOOL_VOCAB_SOURCE
    tools, toolsets = set(), set()
    path = os.path.join(repo, "toolsets.py")
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                tree = ast.parse(fh.read())
        except (OSError, SyntaxError, ValueError):
            tree = None
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, (ast.List, ast.Tuple)):
                    for el in node.elts:
                        if isinstance(el, ast.Constant) and isinstance(el.value, str) \
                                and re.fullmatch(r"[a-z][a-z0-9_]{1,40}", el.value):
                            tools.add(el.value)
                elif isinstance(node, ast.Dict):
                    for key in node.keys:
                        if isinstance(key, ast.Constant) and isinstance(key.value, str) \
                                and re.fullmatch(r"[a-z][a-z0-9_]{1,40}", key.value):
                            toolsets.add(key.value)
    discovered = bool(tools)
    if not discovered:
        for group in (NARROW_TOOLS, MEDIUM_TOOLS, WIDE_TOOLS):
            tools |= group
        tools |= SHELL_TOOLS | DELEGATION_TOOLS
    tools -= NEVER_TOOLS
    ALL_TOOLS = tools
    TOOL_WORDS.clear()
    TOOL_WORDS.update({
        t: re.compile(r"(?<![\w-])" + re.escape(t) + r"(?![\w-])", re.I)
        for t in sorted(ALL_TOOLS)
    })
    AMBIGUOUS = (PROSE_TOOLS | toolsets) & ALL_TOOLS
    TOOL_VOCAB_SOURCE = "toolsets.py" if discovered else "builtin-fallback"
    return discovered

# CLIs whose use implies egress from `terminal`/`execute_code`.
NETWORK_CLIS = {
    "curl", "wget", "gh", "ssh", "scp", "rsync", "aws", "gcloud", "az", "kubectl",
    "docker", "podman", "skopeo", "helm", "terraform", "xurl", "yt-dlp", "himalaya",
    "gws", "openai", "nslookup", "dig", "ping", "whois", "npm", "npx", "uv", "go",
    "cargo", "mail", "sendmail", "stripe", "rclone", "psql", "mysql", "redis-cli",
    "mongosh", "claude", "codex", "gemini", "opencode", "aider",
}
LOCAL_CLIS = {
    "python", "python3", "pip", "pip3", "jq", "ffmpeg", "git", "bash", "sh", "zsh",
    "brew", "apt", "apt-get", "systemctl", "s6-svc", "tmux", "pdftotext", "openssl",
    "gpg", "java", "sbt",
}
# A shell command whose destination is open-world: any host, any repo, any
# image, any cluster. These make `terminal` wide. Package installers
# (pip/npm/uv/apt/brew/...) are NOT here: an install is install-time, and
# `npm run dev` reaches nothing. Network CLIs that talk to a nameable service
# (gh, gws, stripe, curl to a fixed URL) leave `terminal` medium.
UNBOUNDED_CLIS = {
    "ssh", "scp", "rsync", "docker", "podman", "skopeo", "kubectl", "helm",
    "terraform", "rclone", "aws", "gcloud", "az", "mail", "sendmail", "yt-dlp",
    "claude", "codex", "gemini", "opencode", "aider",
}
CLIS = sorted(NETWORK_CLIS | LOCAL_CLIS)
CLI_WORDS = {c: re.compile(r"(?<![\w-])" + re.escape(c) + r"(?![\w-])") for c in CLIS}
CLI_START = re.compile(r"^\s*(?:[$>]\s*)?(?:sudo\s+)?(" +
                       "|".join(re.escape(c) for c in CLIS) + r")(?![\w-])")

CODE_EXT = {
    ".py", ".sh", ".bash", ".zsh", ".fish", ".js", ".mjs", ".cjs", ".ts", ".tsx",
    ".rb", ".go", ".rs", ".java", ".pl", ".php", ".ps1", ".lua", ".r", ".sql",
    ".c", ".cpp", ".h", ".hpp", ".kt", ".swift",
}
CONF_EXT = {".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".conf", ".env"}
BINARY_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".woff", ".woff2", ".ttf",
    ".eot", ".zip", ".gz", ".tgz", ".bz2", ".xz", ".mp3", ".mp4", ".wav", ".ogg",
    ".webp", ".bmp", ".so", ".dylib", ".dll", ".pyc", ".bin", ".exe", ".class",
    ".jar", ".npy", ".npz", ".pt", ".pth", ".onnx", ".parquet", ".sqlite", ".db",
}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache",
             ".pytest_cache", ".ruff_cache", "dist", "build"}

URL_RE = re.compile(r"(?:https?|wss?)://[^\s\"'<>`)\]},;]+")
FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
INLINE_CODE_RE = re.compile(r"`[^`]+`")
ENV_RE = re.compile(
    r"(?:os\.environ(?:\.get)?|os\.getenv|getenv|environ|process\.env|env\[)"
    r"\s*\(?\s*[\"']?([A-Z][A-Z0-9_]{2,})"
)
IMPORT_FROM_RE = re.compile(r"^\s*from\s+([A-Za-z_][\w.]*)", re.M)
IMPORT_RE = re.compile(r"^\s*import\s+(.+)$", re.M)
NET_IMPORT_RE = re.compile(
    r"^\s*(?:import|from)\s+(requests|httpx|aiohttp|urllib|urllib3|http\.client|"
    r"socket|boto3|botocore|tweepy|websockets|paramiko|ftplib|smtplib|yfinance|"
    r"web3|openai|anthropic|google\.generativeai)\b", re.M)
_INSTALL_CMD = (
    r"(?:pip3?\s+install|python3?\s+-m\s+pip\s+install|npm\s+(?:i|install)|"
    r"pnpm\s+add|yarn\s+add|uv\s+(?:pip\s+)?(?:install|add|sync)|git\s+clone|"
    r"apt(?:-get)?\s+install|brew\s+install|go\s+install|cargo\s+install|"
    r"docker\s+(?:pull|run)|gh\s+repo\s+clone|npx\s+|uvx\s+|pipx\s+install|"
    r"curl[^\n|]*\|\s*(?:ba)?sh|wget[^\n]*\|\s*(?:ba)?sh|conda\s+install|"
    r"gem\s+install|rustup\s+)"
)
# An install command at the start of a line (optionally after a shell prompt).
INSTALL_RE = re.compile(r"^\s*(?:[$>]\s*)?(?:sudo\s+)?" + _INSTALL_CMD + r"\b", re.I)
# The same command anywhere, used together with an inline code span so that
# `npm install -g x` written inside prose still counts as install-time.
INSTALL_INLINE_RE = re.compile(_INSTALL_CMD + r"\b", re.I)
# constructs that mean "this line is code/command", not prose
CODEY_RE = re.compile(
    r"(?:requests|httpx)\.(?:get|post|put|delete)|urlopen\s*\(|fetch\s*\(|"
    r"http\.client|socket\.(?:socket|create_connection)|\bcurl\s+https?://|"
    r"\bwget\s+https?://|\bgit\s+clone|\burl\s*=\s*[\"']https?://",
    re.I)
NET_WRITE_RE = re.compile(
    r"\b(?:POST|PUT|PATCH|DELETE)\b|\bgit\s+push\b|\bgh\s+pr\s+create\b|\bscp\s+|"
    r"\brsync\s+|requests\.post|httpx\.post|\bcurl\b[^\n|]*-X\s*(?:POST|PUT|PATCH|DELETE)|"
    r"\b(?:upload|publish)\w*\b|\bsmtplib\b|\bsendmail\b|\bhermes\s+send\b",
    re.I)
LOCAL_WRITE_RE = re.compile(
    r"write_file|open\([^)]*[\"'][wa]|mkdir|>\s*/|\btee\s|shutil\.|\.dump\(|"
    r"write_text|os\.rename|\.write\(",
    re.I)
USER_URL_RE = re.compile(
    r"user[-\s](?:supplied|provided|specified)\s+url|arbitrary\s+url|<url>|"
    r"\bURL\s+argument|--url\b|input\s+url|given\s+url|target\s+url",
    re.I)
RAW_SOCKET_RE = re.compile(
    r"\bwhois\b|port\s+43\b|socket\.create_connection|socket\.socket\s*\(|"
    r"\btelnet\b|\bftplib\b|\braw\s+socket\b",
    re.I)
# local_apps is a fixed vocabulary, never a copied source line. Each entry
# names the app plus where it syncs to. Matched only in code/command context.
LOCAL_APP_MAP = [
    (re.compile(r"iMessage|Messages\.app|application\s+[\"']?Messages|\bSMS\b", re.I),
     "Messages", "iCloud/SMS"),
    (re.compile(r"Apple\s?Notes|Notes\.app|application\s+[\"']?Notes", re.I),
     "Notes", "iCloud"),
    (re.compile(r"Apple\s?Reminders|Reminders\.app|application\s+[\"']?Reminders", re.I),
     "Reminders", "iCloud"),
    (re.compile(r"Apple\s?Calendar|Calendar\.app|application\s+[\"']?Calendar", re.I),
     "Calendar", "iCloud"),
    (re.compile(r"Apple\s?Mail|Mail\.app|application\s+[\"']?Mail", re.I), "Mail", None),
    (re.compile(r"Find\s?My|application\s+[\"']?FindMy", re.I), "Find My", "iCloud"),
    (re.compile(r"Keychain|security\s+find-generic-password", re.I), "Keychain", None),
    (re.compile(r"1Password", re.I), "1Password", "1Password cloud"),
    (re.compile(r"Obsidian\s+Sync", re.I), "Obsidian", "Obsidian Sync cloud"),
    (re.compile(r"osascript|AppleScript", re.I), "AppleScript automation", None),
    (re.compile(r"iCloud", re.I), "iCloud", "iCloud"),
]
PLATFORM_RE = {
    "macos": re.compile(r"macOS\b|Mac\b|OSX|/Applications/|darwin|\bHomebrew\b"),
    "linux": re.compile(r"\bLinux\b|/usr/bin|/etc/|\bapt-get\b|\bsystemd\b|\bs6-svc\b|Debian|Ubuntu"),
    "windows": re.compile(r"\bWindows\b|PowerShell|\.ps1\b|winget|\bchoco\b"),
}
CRED_FILE_RE = re.compile(
    r"~?/?(?:\.git-credentials|\.netrc|\.aws/credentials|credentials\.json|"
    r"service-account\.json|id_rsa|\.ssh/config|\bservice_account\b)",
    re.I)
# Anchored secret patterns. The bare `sk-` substring matched task-/risk-.
SECRET_RES = [
    re.compile(r"\bsk-[A-Za-z0-9]{20,}"),
    re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
    re.compile(r"\bgho_[A-Za-z0-9]{36}\b"),
    re.compile(r"\bghs_[A-Za-z0-9]{36}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{20,}"),
]
PLACEHOLDER_HOSTS = {
    "example.com", "example.org", "example.net", "localhost", "127.0.0.1",
    "0.0.0.0", "your-domain.com", "host.docker.internal", "your-server.com",
}


def is_placeholder(host: str) -> bool:
    """Reserved/example hosts are documentation, never runtime candidates."""
    if host in PLACEHOLDER_HOSTS:
        return True
    if re.search(r"(^|\.)example\.(com|org|net|edu)$", host):
        return True
    if host.endswith((".local", ".invalid", ".test", ".localhost")):
        return True
    return host.startswith(("your-", "your_", "my-", "my_", "xxx", "<", "${"))
ARTIFACT_HOST_RE = re.compile(
    r"fonts\.googleapis\.com|fonts\.gstatic\.com|jsdelivr\.net|unpkg\.com|"
    r"cdnjs\.cloudflare\.com|^cdn\.|^static\.", re.I)


def redact(s: str) -> str:
    for rx in SECRET_RES:
        s = rx.sub("[REDACTED]", s)
    return s


def host_of(url: str) -> str:
    """Strip scheme, userinfo, port, query and fragment from a URL."""
    h = re.sub(r"^[a-z]+://", "", url, flags=re.I)
    h = h.split("/")[0].split("@")[-1].split("?")[0].split("#")[0]
    return h.split(":")[0].strip().strip(".").lower()


def git_commit(repo: str) -> str:
    try:
        out = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=20)
        sha = out.stdout.strip()
        return sha if re.fullmatch(r"[0-9a-f]{40}", sha) else "unknown"
    except Exception:
        return "unknown"


def enumerate_skills(repo: str):
    paths = []
    for sub in ("skills", "optional-skills"):
        base = os.path.join(repo, sub)
        if not os.path.isdir(base):
            continue
        for f in glob.glob(os.path.join(base, "**", "SKILL.md"), recursive=True):
            paths.append(os.path.relpath(os.path.dirname(f), repo))
    return sorted(set(paths))


def iter_text_files(path, skipped):
    for root, dirs, files in os.walk(path):
        keep = []
        for d in sorted(dirs):
            if d in SKIP_DIRS:
                skipped["dirs"].append(os.path.relpath(os.path.join(root, d), path))
            else:
                keep.append(d)
        dirs[:] = keep
        for fn in sorted(files):
            fp = os.path.join(root, fn)
            relname = os.path.relpath(fp, path)
            ext = os.path.splitext(fn)[1].lower()
            if ext in BINARY_EXT:
                skipped["binary"].append(relname)
                continue
            try:
                if os.path.getsize(fp) > 400_000:
                    skipped["large"].append(relname)
                    continue
                with open(fp, encoding="utf-8", errors="replace") as fh:
                    yield relname, fh.read()
            except OSError as exc:
                skipped["unreadable"].append(f"{relname}: {exc.__class__.__name__}")


def frontmatter_platforms(skill_dir):
    """Fall back to the skill's own `platforms:` frontmatter when the scan
    found no platform signal in the body."""
    try:
        with open(os.path.join(skill_dir, "SKILL.md"), encoding="utf-8",
                  errors="replace") as fh:
            text = fh.read()
    except OSError:
        return []
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return []
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return []
    plats = fm.get("platforms")
    if isinstance(plats, str):
        plats = [plats]
    if not isinstance(plats, list):
        return []
    known = {"linux", "macos", "windows"}
    return sorted({str(p).lower() for p in plats if str(p).lower() in known})


def tool_context(line: str, name: str) -> bool:
    """A tool name counts only in a tool-call context, not in prose."""
    rx = TOOL_WORDS[name]
    if re.search(r"(?:-\s*)?name\s*:\s*[\"']?" + re.escape(name) + r"[\"']?\b", line, re.I):
        return True
    if re.search(r"tool_call\s*\(", line) and rx.search(line):
        return True
    if re.search(r"tools?\s*:\s*\[", line, re.I) and rx.search(line):
        return True
    for span in INLINE_CODE_RE.findall(line):
        if rx.search(span):
            return True
    if name in AMBIGUOUS:
        m = rx.search(line)
        if m and TOOL_VERB_RE.search(line[:m.start()]):
            return True
    return False


def scan_skill(repo: str, path: str, commit: str):
    src = os.path.join(repo, path)
    skipped = {"large": [], "binary": [], "dirs": [], "unreadable": []}
    runtime, setup, doc_hosts, artifact = {}, {}, set(), set()
    imports, clis, envs, setup_cmds = set(), set(), set(), []
    tool_ctx, tool_bare = set(), set()
    network_cli_seen, network_cli_runtime, unbounded_cli_runtime = False, False, False
    net_write, local_write = False, False
    raw_socket, user_url = False, False
    local_apps, platforms = [], set()
    cred_files = set()
    n_files = 0
    text_parts = []

    for relname, txt in iter_text_files(src, skipped):
        n_files += 1
        text_parts.append(txt)
        ext = os.path.splitext(relname)[1].lower()
        is_code = ext in CODE_EXT or ext in CONF_EXT
        in_fence = False
        for line in txt.splitlines():
            if FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            stripped = line.strip()
            is_install = bool(INSTALL_RE.match(line)) or bool(
                INLINE_CODE_RE.search(line) and INSTALL_INLINE_RE.search(line))
            is_cmd = bool(CLI_START.match(line)) or is_install or \
                bool(re.match(r"^\s*[$>]\s*\S", line))
            code_context = (is_code or in_fence or is_cmd or is_install
                            or bool(CODEY_RE.search(line)))

            # --- URLs: runtime candidates vs documentation -------------------
            for m in URL_RE.finditer(line):
                host = host_of(m.group(0))
                if not host or "." not in host or is_placeholder(host) or "$" in host:
                    continue
                if is_install:
                    setup[host] = {"host": host, "ports": [], "methods": [],
                                   "why": "install-time reference"}
                elif code_context:
                    runtime.setdefault(host, {"host": host, "ports": [], "methods": [],
                                              "why": "referenced in code or command context"})
                elif ARTIFACT_HOST_RE.search(host):
                    artifact.add(host)
                else:
                    doc_hosts.add(host)
            # --- imports -----------------------------------------------------
            for mod in IMPORT_FROM_RE.findall(line):
                imports.add(mod.split(".")[0])
            for m in IMPORT_RE.finditer(line):
                for part in m.group(1).split(","):
                    mod = part.strip().split(" as ")[0].strip().split(".")[0]
                    if re.fullmatch(r"[A-Za-z_][\w]*", mod or ""):
                        imports.add(mod)
            # --- CLIs --------------------------------------------------------
            if code_context:
                for name, rx in CLI_WORDS.items():
                    if rx.search(line):
                        clis.add(name)
                        if name in NETWORK_CLIS:
                            network_cli_seen = True
                            if not is_install:
                                network_cli_runtime = True
                                if name in UNBOUNDED_CLIS:
                                    unbounded_cli_runtime = True
                if NET_WRITE_RE.search(line):
                    net_write = True
                    network_cli_seen = True
                if LOCAL_WRITE_RE.search(line):
                    local_write = True
            # --- tools -------------------------------------------------------
            for name, rx in TOOL_WORDS.items():
                if not rx.search(line):
                    continue
                if tool_context(line, name):
                    tool_ctx.add(name)
                elif name not in AMBIGUOUS and name not in NEVER_TOOLS:
                    tool_bare.add(name)
            # --- env vars / credential file names ---------------------------
            for m in ENV_RE.finditer(line):
                envs.add(m.group(1))
            for m in CRED_FILE_RE.finditer(line):
                cred_files.add(m.group(0))
            # --- signals -----------------------------------------------------
            if code_context:
                if RAW_SOCKET_RE.search(line):
                    raw_socket = True
                for rx, app, syncs in LOCAL_APP_MAP:
                    if rx.search(line):
                        local_apps.append((app, syncs))
            if USER_URL_RE.search(line):
                user_url = True
            for plat, rx in PLATFORM_RE.items():
                if rx.search(line):
                    platforms.add(plat)
            if is_install:
                setup_cmds.append(redact(stripped)[:160])

    all_text = "\n".join(text_parts)
    tools = tool_ctx | tool_bare
    runtime_hosts = sorted(runtime)
    setup_only = [h for h in sorted(setup) if h not in runtime]
    doc_only = sorted(doc_hosts - set(runtime) - set(setup))
    artifact_only = sorted(artifact - set(runtime) - set(setup))
    cred_envs = sorted(e for e in envs if re.search(
        r"KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH|API", e))

    net_import = bool(NET_IMPORT_RE.search(all_text))
    reach = {}
    for t in sorted(tools):
        if t == "delegate_task":
            # Nothing at Stage 1 constrains the child's toolset, so the parent
            # is as wide as whatever the child is handed. `inherits` ranks as
            # medium for shape; `delegation.rule` records what later stages
            # must enforce, not what the scan observed.
            reach[t] = "inherits"
        elif t == "terminal":
            reach[t] = "wide" if (unbounded_cli_runtime or user_url) \
                else ("medium" if network_cli_runtime else "narrow")
        elif t == "execute_code":
            reach[t] = "wide" if (net_import or network_cli_runtime or user_url) \
                else "narrow"
        else:
            reach[t] = classify_reach(t)

    wide_reach = sorted(t for t, r in reach.items() if r == "wide")
    # `inherits` ranks with medium: the floor until a later stage pins the
    # child's toolset.
    RANK = {"narrow": 0, "medium": 1, "inherits": 1, "unknown": 1, "wide": 2}
    tool_max = max((reach[t] for t in tools), key=lambda r: RANK[r], default="narrow")
    # shape = widest of the skill's own code and its tools' reach.
    # raw_sockets stays a flag that requires socket-level enforcement (it
    # bypasses proxy settings) but is not open-world egress, so it does not
    # force wide.
    wide = bool(wide_reach) or (user_url and bool(runtime_hosts)) \
        or len(runtime_hosts) > 8
    medium = (not wide) and (RANK[tool_max] >= 1 or network_cli_runtime or bool(
        runtime_hosts or cred_envs or cred_files or local_apps))
    shape = "wide" if wide else ("medium" if medium else "narrow")

    if net_write:
        side = "external-write"
    elif wide or runtime_hosts:
        side = "external-read"
    elif local_write:
        side = "local-write"
    elif n_files:
        side = "none"
    else:
        side = "unknown"

    if "delegate_task" in tools:
        delegation = {"inherits": "inherits-toolsets", "rule": "narrow-only"}
    else:
        delegation = {"inherits": "none"}

    # Actions: draft one entry per detected write so stage 2 confirms something
    # instead of inventing it.
    actions = []
    if net_write:
        actions.append({
            "name": "external write",
            "class": "write-shared",
            "review_gate": "human",
            "service": runtime_hosts[0] if runtime_hosts else "unknown",
        })
    elif local_write:
        actions.append({"name": "local write", "class": "write-shared",
                        "review_gate": "autorun"})

    local_apps_dedup = {}
    for app_name, syncs in local_apps:
        local_apps_dedup[app_name] = syncs
    platforms_final = sorted(platforms) or frontmatter_platforms(src) or ["unknown"]

    reasoning = (
        f"Deterministic static scan of {n_files} file(s): {len(runtime_hosts)} runtime host(s), "
        f"{len(setup_only)} setup-only host(s), {len(doc_only)} documentation host(s), "
        f"{len(tools)} Hermes tool(s), {len(clis)} CLI(s), {len(envs)} env name(s). "
        f"{'Wide signal: open-world tool, raw socket, or user-supplied URL. ' if wide else ''}"
        f"{'Medium signal: fixed hosts, credentials or local-app IPC. ' if medium else ''}"
        f"{'Install-time commands only. ' if setup_cmds and not runtime_hosts else ''}"
        "Shape is a deterministic baseline; later stages narrow it."
    )

    manifest = {
        "schema": "hermes-security-manifest/v0",
        "skill": os.path.basename(path),
        "path": path,
        "commit": commit,
        "shape": shape,
        "ceiling": None,
        "summary": "Deterministic static baseline; review and dynamic stages pending",
        "actions": actions,
        "tools": [{"name": t, "reach": reach[t]} for t in sorted(tools)],
        "binaries": [{"program": c, "scope": "unknown"} for c in sorted(clis)],
        "resources": {
            "network": {
                "runtime": [runtime[h] for h in runtime_hosts],
                "setup": [{"host": h, "ports": [], "methods": [],
                           "why": "install-time reference"} for h in setup_only],
                "artifact_refs": [{"host": h, "why": "referenced by generated output"}
                                  for h in artifact_only],
                "tool_mediated": sorted(
                    t for t in tools if reach[t] in ("medium", "wide", "inherits")),
                "raw_sockets": raw_socket,
            },
            "disk": {
                "read": sorted({"workspace"}
                               | ({"home"} if re.search(r"~/|\$HOME|/home/|\.hermes|\.config", all_text) else set())
                               | ({"system"} if re.search(r"/etc/|/usr/|/opt/|systemd|launchctl", all_text) else set())),
                "write": sorted(
                    ({"workspace"} if ("write_file" in tools or local_write) else set())
                    | ({"user-specified"} if (local_write and re.search(
                        r"user[- ]specified|USER_PATH|<path>", all_text, re.I)) else set())),
                "est_bytes": "unknown",
            },
            "hardware": {
                "gpu": "unknown",
                "cpu_ram": "unknown",
                "devices": [],
                "platforms": platforms_final,
            },
            "local_apps": [({"name": n, "syncs_to": s} if s else {"name": n})
                           for n, s in local_apps_dedup.items()],
            "credentials": cred_envs + sorted(cred_files),
            "out_of_band": [],
        },
        "side_effects": side,
        "delegation": delegation,
        "escalations": [],
        "provenance": {
            "method": METHOD,
            "confidence": min(0.5, STAGE_CAPS[METHOD]),
            "evidence": ["evidence/static.json"],
            "notes": ["Deterministic static baseline; verify shape, tools and hosts "
                      "against every file before moving to the next stage."],
            "inputs": {
                "files_scanned": n_files,
                "files_skipped": sum(len(v) for v in skipped.values()),
                "hosts_runtime": len(runtime_hosts),
                "hosts_setup": len(setup_only),
                "tools": len(tools),
                "review": None,
                "dynamic": None,
                "backtest": None,
            },
        },
    }

    evidence = {
        "generator": "generate_baseline.py",
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "method": METHOD,
        "commit": commit,
        "files_scanned": n_files,
        "skipped": {k: v for k, v in skipped.items() if v},
        "hosts_found": [{"host": h, "kind": runtime[h]["why"]} for h in runtime_hosts],
        "setup_hosts": setup_only,
        "doc_hosts": doc_only,
        "artifact_hosts": sorted(artifact),
        "imports": sorted(imports),
        "clis": sorted(clis),
        "env_vars": sorted(envs),
        "credential_names": cred_envs + sorted(cred_files),
        "hermes_tools": {"context": sorted(tool_ctx), "bare": sorted(tool_bare)},
        "tool_vocabulary": {"source": TOOL_VOCAB_SOURCE, "names": len(ALL_TOOLS)},
        "tool_reach": reach,
        "setup_commands": sorted(set(setup_cmds)),
        "signals": {
            "raw_sockets": raw_socket,
            "user_supplied_url": user_url,
            "network_cli": network_cli_seen,
            "network_cli_runtime": network_cli_runtime,
            "unbounded_cli_runtime": unbounded_cli_runtime,
            "network_import": net_import,
            "network_write": net_write,
            "local_write": local_write,
            "local_apps": [{"name": n, "syncs_to": s} if s else {"name": n}
                           for n, s in local_apps_dedup.items()],
            "platforms": sorted(platforms),
            "platforms_from_frontmatter": not platforms and platforms_final != ["unknown"],
        },
        "shape_reasoning": reasoning,
    }
    return manifest, evidence


def main(argv=None):
    ap = argparse.ArgumentParser(description="deterministic static census baseline")
    ap.add_argument("--repo", default=os.environ.get("HERMES_AUDIT_REPO", os.getcwd()),
                    help="audited repository root (default: $HERMES_AUDIT_REPO or cwd)")
    ap.add_argument("--out", default=os.environ.get("HERMES_AUDIT_OUT"),
                    help="output root (default: <repo>/security-manifests)")
    ap.add_argument("--schema", help="copy this JSON Schema to <out>/_schema/manifest.v0.json")
    ap.add_argument("--only", help="comma-separated skill paths to limit the scan to")
    args = ap.parse_args(argv)

    repo = os.path.abspath(args.repo)
    out = os.path.abspath(args.out or os.path.join(repo, "security-manifests"))
    if not os.path.isdir(os.path.join(repo, "skills")) and \
       not os.path.isdir(os.path.join(repo, "optional-skills")):
        print(f"error: {repo} has no skills/ or optional-skills/ - pass --repo", file=sys.stderr)
        return 2
    commit = git_commit(repo)
    load_tool_vocabulary(repo)
    print(f"tool vocabulary: {TOOL_VOCAB_SOURCE} ({len(ALL_TOOLS)} names)", flush=True)
    paths = enumerate_skills(repo)
    if args.only:
        want = {p.strip() for p in args.only.split(",")}
        paths = [p for p in paths if p in want]

    if args.schema and os.path.isfile(args.schema):
        os.makedirs(os.path.join(out, "_schema"), exist_ok=True)
        with open(args.schema, encoding="utf-8") as fh:
            schema_text = fh.read()
        with open(os.path.join(out, "_schema", "manifest.v0.json"), "w",
                  encoding="utf-8") as fh:
            fh.write(schema_text)

    counts = {"narrow": 0, "medium": 0, "wide": 0}
    for i, path in enumerate(paths, 1):
        if not os.path.isdir(os.path.join(repo, path)):
            print("MISSING SOURCE:", path)
            continue
        manifest, evidence = scan_skill(repo, path, commit)
        dest = os.path.join(out, path)
        os.makedirs(os.path.join(dest, "evidence"), exist_ok=True)
        with open(os.path.join(dest, "manifest.yaml"), "w", encoding="utf-8") as fh:
            yaml.safe_dump(manifest, fh, sort_keys=False, allow_unicode=True, width=200)
        with open(os.path.join(dest, "evidence", "static.json"), "w", encoding="utf-8") as fh:
            json.dump(evidence, fh, indent=2, ensure_ascii=False)
        counts[manifest["shape"]] += 1
        if i % 25 == 0:
            print(f"{i}/{len(paths)} done", flush=True)
    print(f"repo={repo} commit={commit} skills={len(paths)} shapes={counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
