## 2024-05-18 - [CRITICAL] Hardcoded API Keys in Documentation
**Vulnerability:** A live or structured dummy API key (`new1_03ba774bd5d7490cb30aaa8f63e6a135`) was hardcoded directly inside a documentation file (`social-media/twitterapi-io/SKILL.md`) as an example.
**Learning:** Documentation files (`README.md`, `SKILL.md`) are often overlooked during security audits but can expose actual production secrets or structured tokens if developers copy-paste working configurations directly into them for examples.
**Prevention:** Use generic, clearly identifiable placeholders (like `YOUR_API_KEY_HERE`, `sk_live_12345...`) in all documentation. Ensure secret scanning tools are configured to also scan `.md` files, not just source code.

## 2026-06-25 - [CRITICAL] Path Traversal in Secret Store
**Vulnerability:** The `_resolve` function in `devops/secret-store/scripts/secrets.py` directly appended user-provided secret names to the store path without validation, allowing directory traversal attacks (e.g., `../something`).
**Learning:** Always resolve paths and check if they are relative to the intended base directory using `pathlib`'s `is_relative_to` method to prevent directory traversal. String prefix checks (`startswith`) are vulnerable to sibling directory traversal.
**Prevention:** Use `resolved_path.is_relative_to(resolved_root)` for all user-provided file paths.

## 2026-07-03 - [CRITICAL] SSRF Vulnerability in HTTP Clients
**Vulnerability:** The HTTP client in `media/translate/src/translate/backends/ollama.py` used `urllib.request.urlopen` with user-controlled URLs without validating the scheme, allowing potential Server-Side Request Forgery (SSRF) and local file read access via `file://` or custom schemes.
**Learning:** Standard library HTTP clients like `urllib.request.urlopen` will happily follow non-HTTP schemes (like `file://` or `ftp://`) if not restricted. This is a common pattern across the codebase's standalone scripts that interface with HTTP APIs.
**Prevention:** Always explicitly validate the URL scheme (e.g., `url.lower().startswith(("http://", "https://"))`) before passing it to `urlopen` or similar clients, and use `# nosec B310` only after this validation is implemented.
