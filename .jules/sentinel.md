## 2024-05-18 - [CRITICAL] Hardcoded API Keys in Documentation
**Vulnerability:** A live or structured dummy API key (`new1_03ba774bd5d7490cb30aaa8f63e6a135`) was hardcoded directly inside a documentation file (`social-media/twitterapi-io/SKILL.md`) as an example.
**Learning:** Documentation files (`README.md`, `SKILL.md`) are often overlooked during security audits but can expose actual production secrets or structured tokens if developers copy-paste working configurations directly into them for examples.
**Prevention:** Use generic, clearly identifiable placeholders (like `YOUR_API_KEY_HERE`, `sk_live_12345...`) in all documentation. Ensure secret scanning tools are configured to also scan `.md` files, not just source code.

## 2026-06-25 - [CRITICAL] Path Traversal in Secret Store
**Vulnerability:** The `_resolve` function in `devops/secret-store/scripts/secrets.py` directly appended user-provided secret names to the store path without validation, allowing directory traversal attacks (e.g., `../something`).
**Learning:** Always resolve paths and check if they are relative to the intended base directory using `pathlib`'s `is_relative_to` method to prevent directory traversal. String prefix checks (`startswith`) are vulnerable to sibling directory traversal.
**Prevention:** Use `resolved_path.is_relative_to(resolved_root)` for all user-provided file paths.

## 2026-06-30 - [MEDIUM] Missing URL Scheme Validation in urllib.request
**Vulnerability:** Several modules (`ollama.py`, `search_vault.py`, `draft_email.py`) passed unvalidated URLs to `urllib.request.urlopen`. This could allow Server-Side Request Forgery (SSRF) or local file reads if an attacker controls the URL and uses custom schemes like `file://`. (Bandit B310)
**Learning:** Python's `urllib.request.urlopen` supports arbitrary schemes by default, making it dangerous when handling user-provided or externally configured URLs.
**Prevention:** Always parse the URL (e.g., with `urllib.parse.urlparse`) and explicitly validate that the scheme is constrained to `http` or `https` before opening the connection. Use `# nosec B310` after explicit validation to silence Bandit.
