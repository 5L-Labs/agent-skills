"""nyt CLI: headlines | article | audio | saved. JSON to stdout, errors to stderr."""
from __future__ import annotations
import argparse
import sys
from typing import Optional

from news_reader_base import add_common_flags, emit, wrap

from . import SCHEMA_VERSION
from .article import get_article
from .audio import get_audio
from .client import NYTError
from .headlines import get_headlines
from .saved import get_saved


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="nyt", description="Read NYTimes via the user's session.")
    p.add_argument("--json-errors", action="store_true",
                   help="Accepted before the subcommand (same as the per-subcommand flag).")
    sub = p.add_subparsers(dest="cmd", required=True)

    ph = sub.add_parser("headlines", help="Top articles from personalized homes (1h cache).")
    ph.add_argument("--limit", type=int, default=25, help="Max articles to return (default 25, 0=all).")
    ph.add_argument("--audio-only", action="store_true",
                    help="Only return articles that ship a synthetic-narration MP3.")
    add_common_flags(ph)

    pa = sub.add_parser("article", help="Fetch one article by URL (cached 30d).")
    pa.add_argument("url", help="Full NYT article URL.")
    add_common_flags(pa)

    pad = sub.add_parser("audio", help="Resolve and optionally download the MP3 for an article.")
    pad.add_argument("url", help="Full NYT article URL.")
    pad.add_argument("--download", action="store_true", help="Also download the MP3 to cache.")
    add_common_flags(pad)

    ps = sub.add_parser("saved", help="Check saved status for one or more article URLs.")
    ps.add_argument("--url", action="append", default=[], help="URL to check (repeatable).")
    add_common_flags(ps)

    args = p.parse_args(argv)

    try:
        if args.cmd == "headlines":
            payload = get_headlines(limit=args.limit, audio_only=args.audio_only, no_cache=args.no_cache)
        elif args.cmd == "article":
            payload = wrap(get_article(args.url, no_cache=args.no_cache), SCHEMA_VERSION)
        elif args.cmd == "audio":
            payload = wrap(get_audio(args.url, download=args.download, no_cache=args.no_cache), SCHEMA_VERSION)
        elif args.cmd == "saved":
            payload = get_saved(args.url or None, no_cache=args.no_cache)
        else:
            p.error(f"unknown command {args.cmd}")
            return 1
    except NYTError as e:
        return emit(None, json_errors=args.json_errors, error=e)

    return emit(payload, json_errors=args.json_errors)


if __name__ == "__main__":
    sys.exit(main())
