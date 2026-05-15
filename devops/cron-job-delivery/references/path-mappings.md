# Path Mappings — HERMES_HOME and XDG Locations

## The Two-Tier Path System

Hermes Agent resolves data directories from two sources:

1. **HERMES_HOME environment variable** — read at startup; controls where Hermes stores its own data
2. **XDG default locations** (`~/.config`, `~/.hermes`) — used by third-party tools and some legacy Hermes code paths

If these diverge, data gets fragmented and appears "lost" after container rebuilds or migrations.

## Common Configurations

| HERMES_HOME | Home dir | Effective paths |
|-------------|----------|-----------------|
| unset | `/home/user` | `~/.hermes/` for Hermes data; `~/.config/` for third-party tools |
| `/opt/data` | `/opt/data/home` | `$HERMES_HOME/` for Hermes; `~/.config/` still points to `/opt/data/home/.config` unless symlinked |
| `/opt/data` (with symlinks) | `/opt/data/home` | `$HERMES_HOME/` → `/opt/data/`; `~/.config` → `/opt/data/config/` (consolidated) |

## The Problem (discovered Apr 16, 2026)

The X/Twitter CLI (`x-cli`) stores credentials in `~/.config/x-cli/.env`. When HERMES_HOME was customized to `/opt/data`, `~/.config` still pointed to `/opt/data/home/.config` — outside the persistent data volume. After a container rebuild:

- Hermes data at `/opt/data/` survived
- X credentials at `/opt/data/home/.config/x-cli/.env` were lost
- `youtube-transcript-api` package had to be re-installed

## The Fix: Symlink Both Locations

Consolidate both legacy paths into the persistent storage:

```bash
# 1. Move any existing ~/.hermes content into HERMES_HOME
mv ~/.hermes/* $HERMES_HOME/ 2>/dev/null || true
rmdir ~/.hermes 2>/dev/null || true

# 2. Symlink ~/.hermes → $HERMES_HOME
ln -s $HERMES_HOME ~/.hermes

# 3. Ensure ~/.config points to persistent storage
#    If $HERMES_HOME/config exists, symlink there:
ln -sf $HERMES_HOME/config ~/.config

# 4. Restore any third-party creds from backup or re-auth
```

After this:
- Tools writing to `~/.hermes/` land in `$HERMES_HOME/` (persisted)
- Tools writing to `~/.config/` land in `$HERMES_HOME/config/` (persisted)
- Everything survives container rebuilds as long as `$HERMES_HOME` is on a persistent volume

## Verification

```bash
# Check symlinks
ls -la ~/.hermes   # Should point to $HERMES_HOME or $HERMES_HOME/.hermes
ls -la ~/.config   # Should point to $HERMES_HOME/config

# Confirm x-cli will use the right path
mkdir -p $HERMES_HOME/config/x-cli
ln -sf $HERMES_HOME/.env $HERMES_HOME/config/x-cli/.env   # if keeping .env unified
```

## Notes

- This pattern applies to any multi-instance Hermes deployment where instances share a persistent data volume.
- The `get_hermes_home()` function in `hermes_constants.py` only controls Hermes-owned paths. Third-party tools use XDG defaults independently.
- For new installations, set HERMES_HOME first, then create the symlinks before installing any third-party CLIs (x-cli, yt-dlp, etc.).
