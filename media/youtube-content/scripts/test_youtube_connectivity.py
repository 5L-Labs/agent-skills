#!/usr/bin/env python3
"""Test connectivity to youtube.com to detect cloud IP blocks.

Exit code 0 = reachable, 1 = block/error.
Prints "OK" or error message.
"""
import sys
import urllib.request

try:
    urllib.request.urlopen('https://www.youtube.com', timeout=5)
    print("OK")
    sys.exit(0)
except Exception as e:
    print(f"FAIL: {e}")
    sys.exit(1)
