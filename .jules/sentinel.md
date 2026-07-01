## 2024-05-18 - [CRITICAL] Hardcoded API Keys in Documentation
**Vulnerability:** A live or structured dummy API key (`new1_03ba774bd5d7490cb30aaa8f63e6a135`) was hardcoded directly inside a documentation file (`social-media/twitterapi-io/SKILL.md`) as an example.
**Learning:** Documentation files (`README.md`, `SKILL.md`) are often overlooked during security audits but can expose actual production secrets or structured tokens if developers copy-paste working configurations directly into them for examples.
**Prevention:** Use generic, clearly identifiable placeholders (like `YOUR_API_KEY_HERE`, `sk_live_12345...`) in all documentation. Ensure secret scanning tools are configured to also scan `.md` files, not just source code.

## 2026-06-25 - [CRITICAL] Path Traversal in Secret Store
**Vulnerability:** The `_resolve` function in `devops/secret-store/scripts/secrets.py` directly appended user-provided secret names to the store path without validation, allowing directory traversal attacks (e.g., `../something`).
**Learning:** Always resolve paths and check if they are relative to the intended base directory using `pathlib`'s `is_relative_to` method to prevent directory traversal. String prefix checks (`startswith`) are vulnerable to sibling directory traversal.
**Prevention:** Use `resolved_path.is_relative_to(resolved_root)` for all user-provided file paths.

## 2026-07-01 - [MEDIUM] SSRF and Local File Read via urllib
**Vulnerability:** Multiple scripts (`search_vault.py`, `draft_email.py`, `ollama.py`) passed unvalidated user-controlled URLs to `urllib.request.urlopen`, creating a risk of Server-Side Request Forgery (SSRF) and local file read vulnerabilities (e.g. `file://`).
**Learning:** Python's `urllib.request.urlopen` accepts non-HTTP schemes by default. When handling external URLs or URLs originating from environment variables, assuming the scheme is always safe can lead to arbitrary local file reads.
**Prevention:** Always explicitly validate that the URL scheme is safely constrained (e.g., checking `url.startswith(("http://", "https://"))`) before making HTTP requests. After validating, use `# nosec B310` to document that the scheme has been securely validated.
