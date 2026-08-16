#!/usr/bin/env python3
"""Harvest Europe PMC as a fourth register, free and unmetered.

Europe PMC is the control case for this project's central finding. Unlike
OpenAlex, it carries SEPARATE publication types for the retracted work and for
the notice that announces the retraction:

    "Retracted Publication"      the paper that was withdrawn
    "Retraction of Publication"  the notice announcing it

That distinction is exactly what a register must preserve, and it demonstrates
that collapsing the two is a choice rather than an unavoidable difficulty.

Output: data/raw/europepmc_retracted.jsonl
        data/raw/europepmc_notices.jsonl
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

EMAIL = "fabio@thetesseractacademy.com"
BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "raw")

TARGETS = [
    ("Retracted Publication", "europepmc_retracted.jsonl"),
    ("Retraction of Publication", "europepmc_notices.jsonl"),
]
PAGE = 1000


def fetch(url, tries=6):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": f"scholarly-record-ontology/0.1 (mailto:{EMAIL})"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            wait = min(2 ** attempt, 60)
            print(f"  retry {attempt+1}/{tries} in {wait}s: {e}", file=sys.stderr, flush=True)
            time.sleep(wait)
    raise RuntimeError(f"failed: {url}")


def main():
    os.makedirs(RAW, exist_ok=True)
    for pubtype, outname in TARGETS:
        out = os.path.join(RAW, outname)
        cursor = "*"
        got = 0
        total = None
        with open(out, "w", encoding="utf-8") as fh:
            while True:
                q = urllib.parse.urlencode({
                    "query": f'PUB_TYPE:"{pubtype}"',
                    "format": "json",
                    "pageSize": PAGE,
                    "cursorMark": cursor,
                    "resultType": "core",
                    "email": EMAIL,
                })
                d = fetch(f"{BASE}?{q}")
                if total is None:
                    total = d.get("hitCount")
                    print(f'[{pubtype}] hitCount={total}', flush=True)
                results = d.get("resultList", {}).get("result", [])
                if not results:
                    break
                for r in results:
                    # keep only what the analysis needs
                    fh.write(json.dumps({
                        "id": r.get("id"),
                        "pmid": r.get("pmid"),
                        "doi": r.get("doi"),
                        "title": r.get("title"),
                        "pubType": r.get("pubType"),
                        "journal": (r.get("journalInfo") or {}).get("journal", {}).get("title"),
                        "pubYear": r.get("pubYear"),
                        "commentCorrectionList": r.get("commentCorrectionList"),
                        "_harvest_pubtype": pubtype,
                    }, ensure_ascii=False) + "\n")
                got += len(results)
                nxt = d.get("nextCursorMark")
                if not nxt or nxt == cursor:
                    break
                cursor = nxt
                print(f"  {got}/{total}", flush=True)
                time.sleep(0.1)
        print(f"DONE {outname}: {got} records", flush=True)


if __name__ == "__main__":
    main()
