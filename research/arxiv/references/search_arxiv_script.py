#!/usr/bin/env python3
"""
search_arxiv.py - Search arXiv papers via the API

Usage:
    python search_arxiv.py "query" [--max N] [--sort {date,relevance}]
"""

import sys
import argparse
import xml.etree.ElementTree as ET
import urllib.request
import urllib.parse

def search_arxiv(query, max_results=5, sort_by='submittedDate', sort_order='descending'):
    params = {
        'search_query': f'all:{query}',
        'max_results': max_results,
        'sortBy': sort_by,
        'sortOrder': sort_order
    }
    url = f"https://export.arxiv.org/api/query?{urllib.parse.urlencode(params)}"
    
    # Add a user-agent header to be polite
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; arXiv-search/1.0;)'}
    req = urllib.request.Request(url, headers=headers)
    
    with urllib.request.urlopen(req) as response:
        data = response.read()
    
    return data

def parse_and_print(xml_data):
    ns = {'a': 'http://www.w3.org/2005/Atom'}
    root = ET.fromstring(xml_data)
    
    for i, entry in enumerate(root.findall('a:entry', ns)):
        title = entry.find('a:title', ns).text.strip().replace('\n', ' ')
        arxiv_id = entry.find('a:id', ns).text.strip().split('/abs/')[-1]
        published = entry.find('a:published', ns).text[:10]
        authors = [a.find('a:name', ns).text for a in entry.findall('a:author', ns)]
        summary = entry.find('a:summary', ns).text.strip().replace('\n', ' ')[:200] if entry.find('a:summary', ns) is not None else ''
        cats = [c.get('term') for c in entry.findall('a:category', ns)]
        
        print(f'{i+1}. [{arxiv_id}] {title}')
        print(f'   Authors: {", ".join(authors)[:80]}')
        print(f'   Published: {published} | Categories: {", ".join(cats)[:60]}')
        print(f'   Abstract: {summary}...')
        print(f'   PDF: https://arxiv.org/pdf/{arxiv_id}')
        print()

def main():
    parser = argparse.ArgumentParser(description='Search arXiv papers')
    parser.add_argument('query', help='Search query')
    parser.add_argument('--max', type=int, default=5, help='Maximum results (default: 5)')
    parser.add_argument('--sort', choices=['date', 'relevance'], default='date', help='Sort by (default: date)')
    parser.add_argument('--category', help='Filter by category (e.g., cs.CL)')
    
    args = parser.parse_args()
    
    # Build search query with optional category
    full_query = args.query
    if args.category:
        full_query += f' AND cat:{args.category}'
    
    # Adjust sort parameter for API
    sort_map = {'date': 'submittedDate', 'relevance': 'relevance'}
    sort_by = sort_map[args.sort]
    sort_order = 'descending' if args.sort == 'date' else 'descending'
    
    try:
        xml_data = search_arxiv(full_query, max_results=args.max, sort_by=sort_by, sort_order=sort_order)
        parse_and_print(xml_data)
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()