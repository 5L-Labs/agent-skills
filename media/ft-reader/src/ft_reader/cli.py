"""ft CLI: headlines | article | audio | myft. JSON to stdout, errors to stderr."""
from __future__ import annotations
import argparse
import sys
from typing import Optional

from news_reader_base import add_common_flags, emit, wrap

from . import SCHEMA_VERSION
from .article import get_article
from .audio import get_audio
from .client import FTError
from .headlines import get_headlines
from .myft import get_myft


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="ft", description="Read FT.com via the user's session.")
    p.add_argument("--json-errors", action="store_true",
                   help="Accepted before the subcommand; same as the per-subcommand flag.")
    sub = p.add_subparsers(dest="cmd", required=True)

    ph = sub.add_parser("headlines", help="Top headlines per section (cached 1h + 30d per article).")
    ph.add_argument("--section", help="Restrict to one section id (e.g. world, tech, lex).")
    ph.add_argument("--limit", type=int, default=5, help="Headlines per section (default 5).")
    add_common_flags(ph)

    pa = sub.add_parser("article", help="Fetch one article by UUID or URL (cached 30d).")
    pa.add_argument("ref", help="Article UUID or full FT URL.")
    add_common_flags(pa)

    pad = sub.add_parser("audio", help="Resolve and optionally download the MP3 for an article.")
    pad.add_argument("ref", help="Article UUID or full FT URL.")
    pad.add_argument("--download", action="store_true", help="Also download the MP3 to cache.")
    add_common_flags(pad)

    pm = sub.add_parser("myft", help="List saved (MyFT) articles. Optionally download all available MP3s.")
    pm.add_argument("--limit", type=int, default=50)
    pm.add_argument("--download-audio", action="store_true")
    add_common_flags(pm)

    args = p.parse_args(argv)

    try:
        if args.cmd == "headlines":
            payload = get_headlines(section=args.section, limit=args.limit, no_cache=args.no_cache)
        elif args.cmd == "article":
            payload = wrap(get_article(args.ref, no_cache=args.no_cache), SCHEMA_VERSION)
        elif args.cmd == "audio":
            payload = wrap(get_audio(args.ref, download=args.download, no_cache=args.no_cache), SCHEMA_VERSION)
        elif args.cmd == "myft":
            payload = get_myft(limit=args.limit, download_audio=args.download_audio,
                               no_cache=args.no_cache)
        else:
            p.error(f"unknown command {args.cmd}")
            return 1
    except FTError as e:
        return emit(None, json_errors=args.json_errors, error=e)

    return emit(payload, json_errors=args.json_errors)


if __name__ == "__main__":
    sys.exit(main())
