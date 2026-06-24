## 2024-05-18 - [CRITICAL] Hardcoded API Keys in Documentation
**Vulnerability:** A live or structured dummy API key (`new1_03ba774bd5d7490cb30aaa8f63e6a135`) was hardcoded directly inside a documentation file (`social-media/twitterapi-io/SKILL.md`) as an example.
**Learning:** Documentation files (`README.md`, `SKILL.md`) are often overlooked during security audits but can expose actual production secrets or structured tokens if developers copy-paste working configurations directly into them for examples.
**Prevention:** Use generic, clearly identifiable placeholders (like `YOUR_API_KEY_HERE`, `sk_live_12345...`) in all documentation. Ensure secret scanning tools are configured to also scan `.md` files, not just source code.

## 2026-06-24 - [Path Traversal with pathlib]
**Vulnerability:** Path traversal possible with `pathlib` by passing paths like `../../../../etc/passwd` to a naive `STORE_ROOT / name` logic.
**Learning:** `pathlib`'s `/` operator doesn't protect against `..` traversals. If the resolved path escapes the expected root, it creates a vulnerability when trying to read or write files.
**Prevention:** When preventing path traversal using Python's `pathlib`, always use `resolved_path.is_relative_to(resolved_root)` to ensure the path stays within bounds. Avoid string prefix checks (`startswith`) which can lead to sibling directory traversal.
