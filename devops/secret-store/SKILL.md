---
name: secret-store
description: Canonical secret store at /opt/data/secrets/ — single source of truth for API keys, tokens, cookies, and credentials. Survives container upgrades. Symlinks preserve backward compatibility with all existing paths.
version: 1.0.0
author: Hermes Agent 01
license: Apache-2.0
metadata:
  hermes:
    tags: [secrets, credentials, docker, backup, infrastructure]
    related_skills: [hermes-agent]
---

# Secret Store

All secrets (API keys, tokens, cookies, SSH keys, OAuth tokens) live in one canonical directory: `/opt/data/secrets/`. This is a mounted Docker volume that survives container upgrades. Every original path is symlinked back here so nothing breaks.

## Why

Before the secret store, secrets were scattered across 6+ locations:

- `/opt/data/.hermes/.env` — main Hermes env
- `/opt/data/.hermes/auth.json` — OAuth tokens
- `/opt/data/config/github/.pat` — GitHub PAT
- `/opt/data/config/github/hermes-agent` — SSH key
- `/opt/data/config/x-cli/accounts/*.env` — X/Twitter accounts
- `/opt/data/config/xurl/config.yaml` — xurl config
- `/opt/data/config/ft-cookies.txt` — FT session cookies
- `/opt/data/skills/media/ft-reader/.env` — FT Reader cookie
- Various other `.env` files in skill directories

After a `docker pull` + container restart, `/opt/hermes/` is replaced but `/opt/data/` survives (mounted volume). The secret store lives under `/opt/data/secrets/` so it persists, and symlinks from the original paths keep everything working.

## Directory Structure

```
/opt/data/secrets/
├── README.md              # Human-readable inventory
├── hermes.env             # Main Hermes .env → /opt/data/.hermes/.env
├── auth.json              # OAuth tokens → /opt/data/.hermes/auth.json
├── github.pat             # GitHub PAT → /opt/data/config/github/.pat
├── github-ssh-key         # SSH private key → /opt/data/config/github/hermes-agent
├── github-ssh-key.pub     # SSH public key → /opt/data/config/github/hermes-agent.pub
├── ft-cookie.env          # FT_COOKIE=... → /opt/data/skills/media/ft-reader/.env
├── x-oauth2-tokens.json   # X OAuth2 tokens → /opt/data/config/x-oauth2-tokens.json
├── xurl-config.yaml       # xurl config → /opt/data/config/xurl/config.yaml
└── x-accounts/
    ├── x-cli.env          # X CLI env → /opt/data/config/x-cli/.env
    ├── 5l_labs.env        # X account → /opt/data/config/x-cli/accounts/5l_labs.env
    └── nickjlange.env     # X account → /opt/data/config/x-cli/accounts/nickjlange.env
```

## Conventions

### Naming

- `hermes.env` — the main Hermes environment file (provider keys, API tokens)
- `*.pat` — personal access tokens (single-line, no env wrapper)
- `*-ssh-key` — SSH private keys (no `.pub` needed in name, it's implied)
- `*-cookie.env` — cookie values wrapped in `NAME=value` format for env loading
- `x-*` — X/Twitter-related secrets
- `x-accounts/` — per-account X/Twitter env files

### Permissions

All secret files: `chmod 600`. SSH public keys: `644`.

### Symlinks

Every original path is a symlink → `/opt/data/secrets/`. Use `ln -sf` (force) so the symlink overwrites without needing `rm` first:

```bash
ln -sf /opt/data/secrets/<name> /original/path
```

## Usage for Skills

### Python skills

Use the loader at `scripts/secrets.py`:

```python
import sys
sys.path.insert(0, "/opt/data/skills/devops/secret-store/scripts")
from secrets import load_secret, load_env

# Load a raw secret (single-line file)
github_pat = load_secret("github.pat")

# Load an env-style secret (KEY=VALUE format)
ft_env = load_env("ft-cookie.env")
# Returns dict: {"FT_COOKIE": "spoor-id=..."}
```

### Shell scripts

Source env files directly:

```bash
set -a
source /opt/data/secrets/ft-cookie.env
set +a
```

Or read raw secrets:

```bash
GITHUB_PAT=$(cat /opt/data/secrets/github.pat)
```

### Hermes skills (SKILL.md)

Reference secrets via their symlinked paths. The original paths still work because they're symlinks to the store:

```yaml
# In SKILL.md metadata:
required_environment_variables: [FT_COOKIE]

# In code, use the skill's .env which is symlinked to the store:
# /opt/data/skills/media/ft-reader/.env → /opt/data/secrets/ft-cookie.env
```

## Adding a New Secret

```
# 1. Create the file in the store
echo "VALUE" > /opt/data/secrets/new-secret.env
chmod 600 /opt/data/secrets/new-secret.env

# 2. Symlink from wherever the app/skill expects it
ln -sf /opt/data/secrets/new-secret.env /path/to/app/.env

# 3. Update this skill's inventory (in the SKILL.md directory listing above)
```

## Backup

```bash
tar czf secrets-backup-$(date +%Y%m%d).tar.gz -C /opt/data secrets/
```

The secret store lives on a mounted Docker volume and survives container upgrades automatically. Backup is only needed for host migration or disaster recovery.

## Restore After New Host

```bash
# 1. Extract backup
tar xzf secrets-backup-YYYYMMDD.tar.gz -C /opt/data/

# 2. Recreate symlinks (see directory structure above for the mapping)
ln -sf /opt/data/secrets/hermes.env /opt/data/.hermes/.env
ln -sf /opt/data/secrets/auth.json /opt/data/.hermes/auth.json
ln -sf /opt/data/secrets/github.pat /opt/data/config/github/.pat
ln -sf /opt/data/secrets/github-ssh-key /opt/data/config/github/hermes-agent
ln -sf /opt/data/secrets/github-ssh-key.pub /opt/data/config/github/hermes-agent.pub
ln -sf /opt/data/secrets/ft-cookie.env /opt/data/skills/media/ft-reader/.env
ln -sf /opt/data/secrets/x-oauth2-tokens.json /opt/data/config/x-oauth2-tokens.json
ln -sf /opt/data/secrets/xurl-config.yaml /opt/data/config/xurl/config.yaml
ln -sf /opt/data/secrets/x-accounts/x-cli.env /opt/data/config/x-cli/.env
ln -sf /opt/data/secrets/x-accounts/5l_labs.env /opt/data/config/x-cli/accounts/5l_labs.env
ln -sf /opt/data/secrets/x-accounts/nickjlange.env /opt/data/config/x-cli/accounts/nickjlange.env

# 3. Fix permissions
chmod 600 /opt/data/secrets/*
chmod 644 /opt/data/secrets/*.pub
```

## Hermes Agent Memory

When Hermes needs to access a credential:

1. If a skill is available for the task, the skill's SKILL.md documents which env vars it needs
2. Those env vars are in the secret store and symlinked to the skill's `.env`
3. If no skill exists, check `/opt/data/secrets/README.md` for the inventory
4. Load secrets via `source`, `cat`, or the Python loader — never hardcode paths to old locations

## Version History

- 1.0.0 (2026-06-08): Initial release. Migrated 12 secrets from 6+ scattered locations into unified `/opt/data/secrets/` directory with symlinks.
