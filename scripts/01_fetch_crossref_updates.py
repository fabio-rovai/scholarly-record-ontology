#!/usr/bin/env python3
"""Harvest every Crossref work carrying a corrective update assertion.

Crossref represents corrections/retractions with an `update-to` array on the
*asserting* record. We deep-page each corrective update-type with a cursor and
store the raw assertions so downstream analysis can reason about who asserts
what about which DOI.

Output: data/raw/crossref_updates.jsonl (one work per line)
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

MAILTO = "fabio@thetesseractacademy.com"
BASE = "https://api.crossref.org/works"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "crossref_updates.jsonl")

# Corrective-signal update types. `retration` is a real misspelling present in
# live Crossref production metadata and is harvested deliberately.
UPDATE_TYPES = [
    "retraction",
    "retration",
    "partial_retraction",
    "expression_of_concern",
    "withdrawal",
    "removal",
    "correction",
    "corrigendum",
    "erratum",
    "corrected",
    "err",
    "addendum",
    "clarification",
]

SELECT = "DOI,update-to,publisher,member,type,issued,container-title,ISSN,title"
ROWS = 1000


def fetch(url, tries=6):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": f"scholarly-record-ontology/0.1 (mailto:{MAILTO})"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # transient API failure
            wait = 2 ** attempt
            print(f"  retry {attempt+1}/{tries} in {wait}s: {e}", file=sys.stderr, flush=True)
            time.sleep(wait)
    raise RuntimeError(f"failed after {tries} tries: {url}")


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    seen = set()
    written = 0
    with open(OUT, "w", encoding="utf-8") as fh:
        for utype in UPDATE_TYPES:
            cursor = "*"
            got = 0
            total = None
            while True:
                q = urllib.parse.urlencode({
                    "filter": f"update-type:{utype}",
                    "rows": ROWS,
                    "cursor": cursor,
                    "select": SELECT,
                    "mailto": MAILTO,
                })
                msg = fetch(f"{BASE}?{q}")["message"]
                if total is None:
                    total = msg.get("total-results", 0)
                    print(f"[{utype}] total-results={total}", flush=True)
                items = msg.get("items", [])
                if not items:
                    break
                for it in items:
                    key = (it.get("DOI"), utype)
                    if key in seen:
                        continue
                    seen.add(key)
                    it["_harvest_update_type"] = utype
                    fh.write(json.dumps(it, ensure_ascii=False) + "\n")
                    written += 1
                got += len(items)
                cursor = msg.get("next-cursor")
                if not cursor:
                    break
                print(f"  [{utype}] {got}/{total}", flush=True)
                time.sleep(0.05)
    print(f"DONE wrote {written} records to {OUT}", flush=True)


if __name__ == "__main__":
    main()
