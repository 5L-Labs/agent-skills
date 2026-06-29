## 2024-05-18 - [CRITICAL] Hardcoded API Keys in Documentation
**Vulnerability:** A live or structured dummy API key (`new1_03ba774bd5d7490cb30aaa8f63e6a135`) was hardcoded directly inside a documentation file (`social-media/twitterapi-io/SKILL.md`) as an example.
**Learning:** Documentation files (`README.md`, `SKILL.md`) are often overlooked during security audits but can expose actual production secrets or structured tokens if developers copy-paste working configurations directly into them for examples.
**Prevention:** Use generic, clearly identifiable placeholders (like `YOUR_API_KEY_HERE`, `sk_live_12345...`) in all documentation. Ensure secret scanning tools are configured to also scan `.md` files, not just source code.

## 2026-06-25 - [CRITICAL] Path Traversal in Secret Store
**Vulnerability:** The `_resolve` function in `devops/secret-store/scripts/secrets.py` directly appended user-provided secret names to the store path without validation, allowing directory traversal attacks (e.g., `../something`).
**Learning:** Always resolve paths and check if they are relative to the intended base directory using `pathlib`'s `is_relative_to` method to prevent directory traversal. String prefix checks (`startswith`) are vulnerable to sibling directory traversal.
**Prevention:** Use `resolved_path.is_relative_to(resolved_root)` for all user-provided file paths.

## 2026-06-29 - [CRITICAL] Missing URL Scheme Validation Allowing SSRF/Local File Read
**Vulnerability:** Calls to `urllib.request.urlopen` were made with user-provided or environment-provided URLs without validating the URL scheme (Bandit B310). This allows an attacker to potentially supply URLs with schemes like `file://` to read local files, or unexpected schemes leading to Server-Side Request Forgery (SSRF) or unexpected application behavior.
**Learning:** Using standard HTTP client libraries without strict validation of the protocol scheme is dangerous when URLs are fully or partially controlled by external configuration or input. Even if standard usage implies HTTP/HTTPS, libraries like `urllib` will gleefully process `file://` unless explicitly told not to.
**Prevention:** Always validate that external URLs start with expected, safe protocols (e.g., `url.startswith(("http://", "https://"))`) before passing them to HTTP clients like `urllib.request.urlopen`.
