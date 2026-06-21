# AGENTS.md — secret-store

Entrypoint for any agent following the AGENTS.md convention (Hermes, Codex, Cursor, Aider, etc.).

## Invocation

This skill is a reference document + loader library. No CLI. Agents should:

1. Read `SKILL.md` for the inventory and conventions
2. Use `scripts/secrets.py` to load secrets programmatically
3. Reference symlinked paths for tools that need original locations

## Python loader

```python
import sys
sys.path.insert(0, "/opt/data/skills/devops/secret-store/scripts")
from secrets import load_secret, load_env, list_secrets

# Load a raw secret (single-line file, returns str)
pat = load_secret("github.pat")

# Load an env-style secret (KEY=VALUE format, returns dict)
ft = load_env("ft-cookie.env")
# ft == {"FT_COOKIE": "spoor-id=..."}

# List all available secrets
all_secrets = list_secrets()
# Returns dict of filename → absolute path
```

## Shell usage

```bash
# Source env-style secrets
set -a && source /opt/data/secrets/ft-cookie.env && set +a

# Read raw secrets
GITHUB_PAT=$(cat /opt/data/secrets/github.pat)

# List all secrets
ls /opt/data/secrets/
```

## Key paths

- Store root: `/opt/data/secrets/`
- Loader: `/opt/data/skills/devops/secret-store/scripts/secrets.py`
- This doc: `/opt/data/skills/devops/secret-store/AGENTS.md`

## When to use this skill

- Any task that needs API keys, tokens, or credentials
- Before running tools that authenticate (xurl, ft-reader, gh, etc.)
- When adding a new secret to the system
- When debugging authentication failures — check the store first
- When migrating to a new host or restoring from backup
