## 2024-05-18 - [CRITICAL] Hardcoded API Keys in Documentation
**Vulnerability:** A live or structured dummy API key (`new1_03ba774bd5d7490cb30aaa8f63e6a135`) was hardcoded directly inside a documentation file (`social-media/twitterapi-io/SKILL.md`) as an example.
**Learning:** Documentation files (`README.md`, `SKILL.md`) are often overlooked during security audits but can expose actual production secrets or structured tokens if developers copy-paste working configurations directly into them for examples.
**Prevention:** Use generic, clearly identifiable placeholders (like `YOUR_API_KEY_HERE`, `sk_live_12345...`) in all documentation. Ensure secret scanning tools are configured to also scan `.md` files, not just source code.

## 2025-02-28 - [CRITICAL] Path Traversal in Secret Store
**Vulnerability:** The `_resolve(name)` function in `devops/secret-store/scripts/secrets.py` appended user input directly to `STORE_ROOT` and iterated through subdirectories without checking if the resolved path was actually inside the target directory. This allowed a path traversal attack where secrets like `../../etc/passwd` or `/etc/passwd` could be resolved.
**Learning:** Even internal helper tools that load secrets need to validate paths to prevent sibling directory traversal or absolute path injection.
**Prevention:** Use Python's `pathlib.Path.resolve()` and `is_relative_to()` to guarantee that resolved paths remain firmly inside the intended root directory.
