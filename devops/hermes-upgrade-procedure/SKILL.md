---
name: hermes-upgrade-procedure
description: Step-by-step procedure to upgrade Hermes Agent from the current version to the latest-1 release tag — backup, replace code, re-apply custom patches, verify.
version: 1.0.0
author: Hermes Agent
tags: [hermes, upgrade, docker, backup, deployment]
---

# Hermes Agent Upgrade Procedure

## When to Upgrade

Upgrade when there's a new release. We always target **latest-1** (the second-most-recent tag) — not the bleeding edge, but not more than one version behind.

## Step 0: Check Current Version & Latest-1 Tag

Run this from the host or inside the container to find your upgrade target:

```bash
# Our current version
grep "^version" /opt/hermes/pyproject.toml

# Latest and latest-1 tags from upstream
cd /opt/data/upstream-hermes-agent
git fetch --tags origin
LATEST=$(git tag -l 'v*' --sort=-version:refname | head -1)
LATEST_MINUS_1=$(git tag -l 'v*' --sort=-version:refname | head -2 | tail -1)
echo "Latest:     $LATEST"
echo "Latest-1:   $LATEST_MINUS_1 (target)"
```

If current version already matches latest-1 (or is newer), no upgrade needed.

## Overview

The code is installed from source at `/opt/hermes/` (no git repo), so the upgrade is a source-replace operation from the upstream clone at `/opt/data/upstream-hermes-agent/`.

**All custom work lives on the mounted Docker volume — NO data backup needed.** Cron jobs, sessions, config, .env, skills (git repo), scripts, auth tokens, work queue, and logs are all on the mounted volume and survive the upgrade automatically.

**The only custom file inside `/opt/hermes/`** is `docker/entrypoint.sh` with a one-line PYTHONPATH fix for an old discord.py workaround. This is likely obsolete in v0.14.0+.

## Prerequisites

- Upstream clone at `/opt/data/upstream-hermes-agent/` with tags fetched
- Ability to stop/start the Docker container

## Known Bind Mounts

| Host path | Container path | What lives there |
|-----------|---------------|------------------|
| `/data/agents/hermes-01/hermes/` | `/opt/data` | HERMES_HOME — config, cron, sessions, auth, work queue |
| `/data/agents/hermes-01/.hermes` | `/root/.hermes/` | (symlinked to /opt/data/.hermes in practice) |
| `/data/agents/hermes-01/.config/` | `/root/.config/` | Tool configs |
| `/data/workbench/` | `/data/workbench/` | Output/backup workbench |

## Step 1: Backup the Entrypoint (Only Custom File)

Our only customization to `/opt/hermes/` source code:

- **`/opt/hermes/docker/entrypoint.sh`** — has `export PYTHONPATH="/opt/data/discord-site-packages"` at line 1

This was a workaround for an old discord.py version. Versions after v0.13.0 ship `discord.py==2.7.1` natively, so this fix is likely OBSOLETE. Back it up just in case:

```bash
cp /opt/hermes/docker/entrypoint.sh /data/workbench/entrypoint-v$(grep "^version" /opt/hermes/pyproject.toml | cut -d'"' -f2).sh
```

Everything else in `/opt/hermes/` is upstream's code that changed between versions — not ours to back up.

## What Is NOT at Risk (Auto-Preserved on Mounted Volume)

| Path | Contents | Your custom work |
|------|----------|-----------------|
| `/opt/data/cron/jobs.json` | All cron jobs | x-digest, arxiv, nightly sync, youtube transcript fetches |
| `/opt/data/.hermes/state.db` | Session history | All past conversations |
| `/opt/data/.hermes/auth.json` | OAuth tokens | X/Twitter, Mattermost, Discord, Signal auth |
| `/opt/data/.hermes/config.yaml` | All configuration | Gateway platforms, model settings, delivery targets |
| `/opt/data/.hermes/.env` | API keys and secrets | All provider keys |
| `/opt/data/.hermes/work-queue.md` | Work queue | Pending tasks |
| `/opt/data/.hermes/memories/` | Persistent memory | Session-to-session knowledge |
| `/opt/data/skills/` | Custom skills (separate git repo) | All skills, nightly PR workflow |
| `/opt/data/scripts/` | Nightly sync and other custom scripts | nightly-repo-sync.py |
| `/opt/data/logs/` | Gateway and agent logs | Debug history |

## Step 2: Replace Hermes Source Code

```bash
# Stop the gateway
docker stop <container-name>  # or: systemctl --user stop hermes-gateway

# Readiness check before swap
echo "Checking: upstream tag checked out..."
cd /opt/data/upstream-hermes-agent
LATEST_MINUS_1=$(git tag -l 'v*' --sort=-version:refname | head -2 | tail -1)
git checkout -f "$LATEST_MINUS_1"
grep "^version" pyproject.toml
echo "Target version confirmed. Ready to swap."

# Swap source
rm -rf /opt/hermes.bak
mv /opt/hermes /opt/hermes.bak
cp -r /opt/data/upstream-hermes-agent /opt/hermes
rm -rf /opt/hermes/.git
```

## Step 3: Rebuild the Virtual Environment

```bash
cd /opt/hermes
uv sync --frozen --inexact
```

`uv sync --frozen` uses the lockfile from the release (no dependency resolution, deterministic).
`--inexact` allows the solver to skip packages already satisfied.

## Step 4: Re-Apply Custom Patches (If Still Needed)

Check if the discord.py PYTHONPATH fix is still needed:

```bash
cd /opt/hermes && python3 -c "import discord; print(discord.__version__)"
```

If discord.py loads successfully with version >= 2.7.1, the fix is NOT needed. Skip this step. Otherwise:

```bash
# Restore backup entrypoint with PYTHONPATH
cp /data/workbench/entrypoint-v*.sh /opt/hermes/docker/entrypoint.sh
```

## Step 5: Restart the Gateway

```bash
docker start <container-name>  # or: systemctl --user restart hermes-gateway

# Verify startup
sleep 10
docker logs <container-name> --tail 30
```

## Step 6: Post-Upgrade Verification

```bash
# Check version
docker exec <container-name> hermes --version

# Check running
docker exec <container-name> hermes status

# Verify cron jobs survived
docker exec <container-name> cat /opt/data/cron/jobs.json | head -5

# Verify X auth survived
docker exec <container-name> cat /opt/data/.hermes/auth.json | head -5

# Verify config survived
docker exec <container-name> cat /opt/data/.hermes/config.yaml | head -10

# Check gateway is connected
docker logs <container-name> --tail 30 | grep -i "connected\|platform\|ready"

# Verify Discord adapter works
docker exec <container-name> python3 -c "import discord; print(discord.__version__)"
```

## Step 7: Clean Up (After Confirming Everything Works)

```bash
# Remove old source backup
rm -rf /opt/hermes.bak

# Remove old workaround if no longer needed
rm -rf /opt/data/discord-site-packages
```

## Rollback Plan

If the upgrade fails:

```bash
docker stop <container-name>
rm -rf /opt/hermes
mv /opt/hermes.bak /opt/hermes
docker start <container-name>
```

## Quick Reference: One-Time Upgrade Commands

Here's the full sequence in one block — copy, paste, run:

```bash
# 0. Check version
grep "^version" /opt/hermes/pyproject.toml
cd /opt/data/upstream-hermes-agent && git fetch --tags origin
LATEST_MINUS_1=$(git tag -l 'v*' --sort=-version:refname | head -2 | tail -1)
echo "Target: $LATEST_MINUS_1"

# 1. Backup entrypoint
cp /opt/hermes/docker/entrypoint.sh /data/workbench/entrypoint-$(date +%Y%m%d).sh

# 2. Swap source
docker stop hermes-gateway
rm -rf /opt/hermes.bak
mv /opt/hermes /opt/hermes.bak
cd /opt/data/upstream-hermes-agent && git checkout -f "$LATEST_MINUS_1"
cp -r /opt/data/upstream-hermes-agent /opt/hermes
rm -rf /opt/hermes/.git

# 3. Rebuild venv
cd /opt/hermes && uv sync --frozen --inexact

# 4. Verify discord
python3 -c "import discord; print(discord.__version__)" && echo "OK - no patch needed"

# 5. Start
docker start hermes-gateway
sleep 10
docker logs hermes-gateway --tail 20

# 6. Clean old code
rm -rf /opt/hermes.bak
```
