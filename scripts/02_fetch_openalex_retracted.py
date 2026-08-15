#!/usr/bin/env python3
"""Harvest every work OpenAlex flags as retracted (is_retracted:true).

This is one of the three registers compared in this project. Cursor-paged.

Output: data/raw/openalex_retracted.jsonl
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

MAILTO = "fabio@thetesseractacademy.com"
BASE = "https://api.openalex.org/works"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "openalex_retracted.jsonl")

SELECT = ",".join([
    "id", "doi", "is_retracted", "is_paratext", "publication_year", "publication_date",
    "type", "cited_by_count", "counts_by_year", "primary_location", "referenced_works_count",
])


def fetch(url, tries=10):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": f"scholarly-record-ontology/0.1 (mailto:{MAILTO})"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            wait = min(2 ** attempt, 120)
            print(f"  retry {attempt+1}/{tries} in {wait}s: {e}", file=sys.stderr, flush=True)
            time.sleep(wait)
    raise RuntimeError(f"failed after {tries} tries: {url}")


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    # Resume support: OpenAlex 429s under concurrent load, so allow restarting
    # from the last cursor instead of re-fetching the whole set.
    cursor = sys.argv[1] if len(sys.argv) > 1 else "*"
    mode = "a" if cursor != "*" else "w"
    got = 0
    total = None
    with open(OUT, mode, encoding="utf-8") as fh:
        while True:
            q = urllib.parse.urlencode({
                "filter": "is_retracted:true",
                "per-page": 200,
                "cursor": cursor,
                "select": SELECT,
                "mailto": MAILTO,
            })
            msg = fetch(f"{BASE}?{q}")
            if total is None:
                total = msg["meta"]["count"]
                print(f"total is_retracted:true = {total}", flush=True)
            results = msg.get("results", [])
            if not results:
                break
            for it in results:
                fh.write(json.dumps(it, ensure_ascii=False) + "\n")
            got += len(results)
            cursor = msg["meta"].get("next_cursor")
            if got % 4000 == 0:
                print(f"  {got}/{total}", flush=True)
            if not cursor:
                break
            time.sleep(0.5)
    print(f"DONE wrote {got} records to {OUT}", flush=True)


if __name__ == "__main__":
    main()
