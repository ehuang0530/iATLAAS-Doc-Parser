#!/usr/bin/env python3
"""
Sample script using doc2struct to parse an SEC Form 10-K filing.

Target:
    FactSet Research Systems Inc. (FDS) 2026 Form 10-K
    URL: https://www.sec.gov/Archives/edgar/data/1013237/000162828026066391/fds-20260831.htm
"""

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
import urllib.request

try:
    from doc2struct import parse_html
except ImportError:
    print("Error: doc2struct is not installed in the current Python environment.")
    print("Install it with: pip install doc2struct")
    sys.exit(1)


DEFAULT_URL = "https://www.sec.gov/Archives/edgar/data/1013237/000162828026066391/fds-20260831.htm"
DEFAULT_USER_AGENT = "SampleResearchApp/1.0 (contact@example.com)"


def fetch_filing(url: str, user_agent: str, cache_file: str = "fds-20260831.htm") -> bytes:
    """Fetch filing HTML from SEC EDGAR or read from local cache."""
    cache_path = Path(cache_file)
    if cache_path.exists():
        print(f"[*] Reading cached filing from {cache_path} ({cache_path.stat().st_size:,} bytes)...")
        return cache_path.read_bytes()

    print(f"[*] Downloading filing from {url}...")
    req = urllib.request.Request(
        url,
        headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}
    )
    with urllib.request.urlopen(req) as resp:
        if resp.info().get("Content-Encoding") == "gzip":
            import gzip
            content = gzip.decompress(resp.read())
        else:
            content = resp.read()

    print(f"[*] Downloaded {len(content):,} bytes. Saving to cache '{cache_file}'...")
    cache_path.write_bytes(content)
    return content


def print_summary(elements: list[dict]):
    """Print high-level statistics of the parsed document."""
    counts = Counter(elem.get("type") for elem in elements)
    print("\n" + "=" * 60)
    print(f" DOCUMENT PARSE SUMMARY (Total Elements: {len(elements)})")
    print("=" * 60)
    for elem_type, count in counts.most_common():
        print(f"  - {elem_type:<15}: {count:>5}")

    # SEC items found
    items = [e for e in elements if e.get("class") == "item"]
    print(f"\n  SEC Items Identified: {len(items)}")
    for item in items[:15]:
        title = item.get("standardized_title") or item.get("text")
        print(f"    • [{item.get('id'):>3}] {title}")
    if len(items) > 15:
        print(f"    ... and {len(items) - 15} more items.")


def print_sample_tables(elements: list[dict], limit: int = 3):
    """Print structured table examples with headers, matrices, and metadata."""
    tables = [e for e in elements if e.get("type") == "table"]
    print("\n" + "=" * 60)
    print(f" STRUCTURED TABLES (Displaying {min(limit, len(tables))} of {len(tables)})")
    print("=" * 60)

    for i, t in enumerate(tables[:limit]):
        title = t.get("text") or "Untitled Table"
        print(f"\n[Table #{i + 1} | ID: {t.get('id')} | Depth: {t.get('level')}]")
        print(f" Title     : {title}")
        if t.get("preamble"):
            preamble = t["preamble"].strip().replace("\n", " ")
            print(f" Preamble  : {preamble[:140]}..." if len(preamble) > 140 else f" Preamble  : {preamble}")
        if t.get("cleaned"):
            print(f" Cleaning  : {', '.join(t['cleaned'])}")

        matrix = t.get("matrix") or []
        print(f" Dimensions: {len(matrix)} rows x {len(matrix[0]) if matrix else 0} cols")

        # Print first few rows
        preview_rows = matrix[:5]
        for row_idx, row in enumerate(preview_rows):
            formatted_cells = [c.replace("\n", " ").strip()[:30] for c in row]
            print(f"   Row {row_idx}: {formatted_cells}")
        if len(matrix) > 5:
            print(f"   ... ({len(matrix) - 5} more rows)")

        if t.get("footnotes"):
            print(f" Footnotes : {t['footnotes']}")
        if t.get("postamble"):
            print(f" Postamble : {t['postamble'][:100]}...")


def print_sample_sections(elements: list[dict], limit: int = 5):
    """Print sample text sections and titles."""
    print("\n" + "=" * 60)
    print(f" SAMPLE DOCUMENT HIERARCHY & TEXT")
    print("=" * 60)
    samples = [e for e in elements if e.get("type") in ("title", "text")][:limit]
    for s in samples:
        indent = "  " * s.get("level", 0)
        elem_type = s.get("type")
        text = (s.get("text") or "").strip().replace("\n", " ")
        if len(text) > 120:
            text = text[:120] + "..."
        print(f"{indent}[{elem_type.upper()}] (id={s.get('id')}) {text}")


def main():
    parser = argparse.ArgumentParser(description="Parse SEC Form 10-K using doc2struct")
    parser.add_argument("--url", default=DEFAULT_URL, help="SEC filing HTML URL")
    parser.add_argument("--rules", default="SEC:10-K", help="Preset ruleset (default: SEC:10-K)")
    parser.add_argument("--no-cache", action="store_true", help="Do not use local cache")
    parser.add_argument("--json-out", help="Path to save full output as JSON")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="User-Agent for SEC EDGAR")
    args = parser.parse_args()

    cache_file = "fds-20260831.htm" if not args.no_cache else "/dev/null"
    html_bytes = fetch_filing(args.url, args.user_agent, cache_file)

    print(f"[*] Parsing with doc2struct (rules='{args.rules}')...")
    structured_output = parse_html(html_bytes, rules=args.rules)
    print(f"[+] Successfully parsed {len(structured_output)} structured elements!")

    print_summary(structured_output)
    print_sample_sections(structured_output, limit=6)
    print_sample_tables(structured_output, limit=3)

    if args.json_out:
        out_path = Path(args.json_out)
        print(f"\n[*] Exporting structured output to {out_path}...")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(structured_output, f, indent=2, ensure_ascii=False)
        print(f"[+] Exported {out_path.stat().st_size:,} bytes to {out_path}")


if __name__ == "__main__":
    main()

