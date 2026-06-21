"""`translate` CLI: read JSON from stdin, translate selected string fields, write JSON to stdout."""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__, cache as cache_mod
from .backends import get_backend
from .walker import DEFAULT_FIELDS, is_already_translated, iter_strings


EXIT_OK = 0
EXIT_BAD_INPUT = 2
EXIT_BACKEND = 4


def _safe_cache_get(*args, **kwargs):
    try:
        return cache_mod.get(*args, **kwargs)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] cache read failed: {type(e).__name__}: {e}", file=sys.stderr)
        return None


def _safe_cache_put(*args, **kwargs) -> None:
    """A cache write failure must never abort an otherwise-successful translation run."""
    try:
        cache_mod.put(*args, **kwargs)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] cache write failed: {type(e).__name__}: {e}", file=sys.stderr)


def _parse_fields(spec: str | None) -> frozenset[str]:
    if not spec:
        return DEFAULT_FIELDS
    keep = set(DEFAULT_FIELDS)
    for tok in spec.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if tok.startswith("+"):
            keep.add(tok[1:])
        elif tok.startswith("-"):
            keep.discard(tok[1:])
        else:
            return frozenset(t.strip() for t in spec.split(",") if t.strip())
    return frozenset(keep)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="translate", description=__doc__)
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    ap.add_argument("--target", required=True, help="Target language code (e.g. en, zh, ja).")
    ap.add_argument("--source", default="auto", help="Source language code or 'auto'.")
    ap.add_argument("--backend", help="Backend name (default: env TRANSLATE_BACKEND or 'ollama').")
    ap.add_argument("--model", help="Model id (default: env TRANSLATE_MODEL).")
    ap.add_argument("--field", help="Comma list of fields to translate. Use +x to add, -x to drop, or bare names to replace.")
    ap.add_argument("--inplace", action="store_true", help="Replace source strings rather than add `_<lang>` siblings.")
    ap.add_argument("--no-cache", action="store_true", help="Bypass translation cache read+write.")
    args = ap.parse_args(argv)

    try:
        doc = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"[err] bad JSON on stdin: {e}", file=sys.stderr)
        return EXIT_BAD_INPUT

    backend = get_backend(args.backend, model=args.model)
    fields = _parse_fields(args.field)
    cache_dir = cache_mod.default_cache_dir()
    sig = backend.cache_signature()
    n_total = 0
    n_hit = 0
    n_translated = 0
    n_error = 0

    for container, key, value in iter_strings(doc, fields=fields):
        if not args.inplace and is_already_translated(container, key, args.target):
            continue
        n_total += 1
        translation: str | None = None
        if not args.no_cache:
            translation = _safe_cache_get(cache_dir, value, args.source, args.target, sig)
            if translation is not None:
                n_hit += 1
        if translation is None:
            try:
                translation = backend.translate(value, source=args.source, target=args.target)
                n_translated += 1
            except Exception as e:  # noqa: BLE001
                n_error += 1
                err_key = f"{key}_{args.target}_error"
                container[err_key] = f"{type(e).__name__}: {e}"
                if args.inplace:
                    continue
                container[f"{key}_{args.target}"] = None
                continue
            if not args.no_cache:
                _safe_cache_put(cache_dir, value, args.source, args.target, sig, translation)
        if args.inplace:
            container[key] = translation
        else:
            container[f"{key}_{args.target}"] = translation

    print(
        f"[info] translated total={n_total} cache_hit={n_hit} new={n_translated} errors={n_error}",
        file=sys.stderr,
    )
    json.dump(doc, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return EXIT_OK if n_error == 0 else EXIT_BACKEND


if __name__ == "__main__":
    sys.exit(main())
