## 2024-05-18 - [CRITICAL] Hardcoded API Keys in Documentation
**Vulnerability:** A live or structured dummy API key (`new1_03ba774bd5d7490cb30aaa8f63e6a135`) was hardcoded directly inside a documentation file (`social-media/twitterapi-io/SKILL.md`) as an example.
**Learning:** Documentation files (`README.md`, `SKILL.md`) are often overlooked during security audits but can expose actual production secrets or structured tokens if developers copy-paste working configurations directly into them for examples.
**Prevention:** Use generic, clearly identifiable placeholders (like `YOUR_API_KEY_HERE`, `sk_live_12345...`) in all documentation. Ensure secret scanning tools are configured to also scan `.md` files, not just source code.

## 2026-06-25 - [CRITICAL] Path Traversal in Secret Store
**Vulnerability:** The `_resolve` function in `devops/secret-store/scripts/secrets.py` directly appended user-provided secret names to the store path without validation, allowing directory traversal attacks (e.g., `../something`).
**Learning:** Always resolve paths and check if they are relative to the intended base directory using `pathlib`'s `is_relative_to` method to prevent directory traversal. String prefix checks (`startswith`) are vulnerable to sibling directory traversal.
**Prevention:** Use `resolved_path.is_relative_to(resolved_root)` for all user-provided file paths.
## 2026-06-28 - [MEDIUM] Server-Side Request Forgery via urllib
**Vulnerability:** `urllib.request.urlopen` was used without scheme validation in `OllamaBackend._post_with_retry` (`media/translate/src/translate/backends/ollama.py`). This could allow an SSRF or local file read attack if a malicious host is provided via environment variables (e.g. `OLLAMA_HOST=file:///etc/passwd`).
**Learning:** Always validate that URLs passed to `urllib.request.urlopen` or similar HTTP clients use safe schemes (`http://` or `https://`) to prevent local file access or interaction with unexpected protocols.
**Prevention:** Explicitly check `url.startswith(("http://", "https://"))` before making the request. Additionally, use `# nosec B310` to silence the Bandit warning once the scheme validation is explicitly implemented.
