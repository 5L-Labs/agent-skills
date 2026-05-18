#!/usr/bin/env python3
"""Parse an arXiv category listings HTML file and extract paper metadata.

Usage:
    python parse_listings.py /tmp/cscl_new.html "large language model" --max 5
    python parse_listings.py /tmp/cscl_new.html --author "lecun" --max 10
    python parse_listings.py /tmp/cscl_new.html --abstract "reinforcement learning" --max 5

Outputs tab-separated lines: arxiv_id<TAB>title<TAB>authors<TAB>abstract_snippet
No dependencies — Python stdlib only.
"""
import argparse, re, sys

def parse_args():
    p = argparse.ArgumentParser(description="Parse arXiv category listings HTML")
    p.add_argument("html_file", help="Saved HTML file from arXiv listings page")
    p.add_argument("--query", help="Filter: keyword/phrase in title+abstract")
    p.add_argument("--abstract", help="Filter: keyword/phrase in abstract only")
    p.add_argument("--author", help="Filter: author last name (case-insensitive)")
    p.add_argument("--max", type=int, default=5, help="Max results to print")
    return p.parse_args()

def strip_latex(text: str) -> str:
    """Remove LaTeX commands like \\operatorname{XYZ} from strings."""
    return re.sub(r'\\[a-zA-Z]+\{.*?\}', '', text)

def strip_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    return re.sub(r'<[^>]+>', '', text).replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')

def extract_block(html: str, pid: str, char_radius: int = 4000) -> str:
    """Get the paper block surrounding the second occurrence of 'id=pid'."""
    anchor = f'id="{pid}"'
    idx = html.find(anchor, html.find(anchor) + 1)  # second occurrence
    if idx == -1:
        # Fallback: first occurrence
        idx = html.find(anchor)
    return html[max(0, idx - 50):min(len(html), idx + char_radius)]

def parse_papers(html: str):
    """Return a list of dicts with id, title, authors, abstract."""
    ids_seen = []
    ids = re.findall(r'id="(\d+\.\d+)"', html)
    for pid in ids:
        if pid not in ids_seen:
            ids_seen.append(pid)

    papers = []
    for pid in ids_seen:
        block = extract_block(html, pid)

        # Title
        title_m = re.search(
            r"(?:class=\'descriptor\'>|<span[^>]*>Title:</span>\s*)(.*?)(?:</div>|$)",
            block, re.DOTALL
        )
        title = strip_html(strip_latex(title_m.group(1))).strip() if title_m else ""

        # Authors
        author_raw = re.findall(r'query=([^&"]+?)&amp;', block)
        if not author_raw:
            author_raw = re.findall(r'query=([^,\"]+),', block)
        authors = []
        for a in author_raw:
            raw = a.replace('+', ' ').strip()
            if raw and raw not in authors:
                authors.append(raw)

        # Abstract
        abs_m = re.search(r"class='mathjax'>(.*?)</p>", block, re.DOTALL)
        abstract_unstripped = strip_html(abs_m.group(1)).strip() if abs_m else ""
        abstract = re.sub(r'\s+', ' ', abstract_unstripped)[:500]

        papers.append({
            'id': pid,
            'title': title,
            'authors': authors,
            'abstract': abstract,
        })
    return papers

def main():
    args = parse_args()

    with open(args.html_file, encoding="utf-8") as f:
        html = f.read()

    papers = parse_papers(html)

    # Apply filters
    if args.query:
        q = args.query.lower()
        papers = [p for p in papers
                  if q in (p['title'] + ' ' + p['abstract']).lower()]
    if args.abstract:
        a = args.abstract.lower()
        papers = [p for p in papers if a in p['abstract'].lower()]
    if args.author:
        au = args.author.lower()
        papers = [p for p in papers
                  if any(au in a.lower() for a in p['authors'])]

    papers = papers[:args.max]

    for p in papers:
        authors_str = ", ".join(p['authors'][:5])
        print(f"{p['id']}\t{p['title']}\t{authors_str}\t{p['abstract'][:200]}")

if __name__ == "__main__":
    main()
