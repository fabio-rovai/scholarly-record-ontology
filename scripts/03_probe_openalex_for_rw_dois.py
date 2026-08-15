#!/usr/bin/env python3
"""Probe OpenAlex for every Retraction Watch original-paper DOI.

The point: a DOI that Retraction Watch records as retracted may be

  (a) present in OpenAlex AND flagged is_retracted  -> signal propagated
  (b) present in OpenAlex AND NOT flagged           -> SILENT FAILURE
  (c) absent from OpenAlex entirely                 -> not indexed

Case (b) is the finding this project exists to measure: the work is in the
graph everyone queries, and the graph does not know it is retracted.

Output: data/raw/openalex_rw_probe.jsonl  (resumable)
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

import pandas as pd

MAILTO = "fabio@thetesseractacademy.com"
BASE = "https://api.openalex.org/works"
HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
OUT = os.path.join(RAW, "openalex_rw_probe.jsonl")

SELECT = "id,doi,is_retracted,publication_year,cited_by_count,counts_by_year,type,primary_location"
BATCH = 40
# DOIs containing these break the pipe-delimited OR filter syntax.
UNSAFE = re.compile(r"[|,\s]")


def norm_doi(v):
    if not isinstance(v, str):
        return None
    v = v.strip().lower()
    if not v or v in {"unavailable", "nan", "none"}:
        return None
    v = re.sub(r"^https?://(dx\.)?doi\.org/", "", v)
    v = re.sub(r"^doi:", "", v)
    if not v.startswith("10."):
        return None
    return v


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
    return None


def main():
    rw = pd.read_csv(os.path.join(RAW, "retraction_watch.csv"), dtype=str, keep_default_na=False)
    dois = []
    seen = set()
    for v in rw["OriginalPaperDOI"]:
        d = norm_doi(v)
        if d and d not in seen and not UNSAFE.search(d):
            seen.add(d)
            dois.append(d)
    print(f"unique probe-safe RW original DOIs: {len(dois)}", flush=True)

    done = set()
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as fh:
            for line in fh:
                try:
                    done.add(json.loads(line)["_probe_doi"])
                except Exception:
                    pass
        print(f"resuming, {len(done)} already probed", flush=True)

    todo = [d for d in dois if d not in done]
    print(f"to probe: {len(todo)}", flush=True)

    with open(OUT, "a", encoding="utf-8") as fh:
        for i in range(0, len(todo), BATCH):
            chunk = todo[i:i + BATCH]
            q = urllib.parse.urlencode({
                "filter": "doi:" + "|".join(chunk),
                "per-page": 200,
                "select": SELECT,
                "mailto": MAILTO,
            })
            msg = fetch(f"{BASE}?{q}")
            if msg is None:
                print(f"  SKIP batch at {i} (persistent failure)", file=sys.stderr, flush=True)
                continue
            found = {}
            for it in msg.get("results", []):
                d = norm_doi(it.get("doi"))
                if d:
                    found[d] = it
            for d in chunk:
                rec = found.get(d)
                out = {"_probe_doi": d, "_found": rec is not None}
                if rec:
                    out.update(rec)
                fh.write(json.dumps(out, ensure_ascii=False) + "\n")
            if (i // BATCH) % 50 == 0:
                print(f"  {i + len(chunk)}/{len(todo)}", flush=True)
            time.sleep(0.4)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
