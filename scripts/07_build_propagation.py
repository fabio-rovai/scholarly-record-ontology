#!/usr/bin/env python3
"""Populate the propagation layer: what a citator for science would actually flag.

For the most-cited retracted works, fetch every citing work from OpenCitations
and grade it against the retraction date:

    severe   the citation post-dates the retraction. The citing author had, in
             principle, the means to know.
    caution  the citation pre-dates the retraction. Not a fault, but the citing
             work now rests on withdrawn evidence and its readers are not told.

This is the layer legal publishing has had since 1873 and the scholarly record
has never had.

Outputs:
  data/derived/propagation.json          summary and worst cases
  data/graph/sro-propagation.nt.gz       CitationEvent + PropagationSignal triples
"""
import gzip
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
DERIVED = os.path.join(HERE, "..", "data", "derived")
GRAPH = os.path.join(HERE, "..", "data", "graph")

SRO = "https://ontology.tesseract.academy/sro/"
BASE = SRO + "id/"
XSD = "http://www.w3.org/2001/XMLSchema#"
RDFT = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
OC = "https://opencitations.net/index/api/v1/citations/"

TOP_N = int(os.environ.get("SRO_TOP_N", "400"))
WORKERS = 4


def norm_doi(v):
    if not isinstance(v, str):
        return None
    v = v.strip().lower()
    if not v or v in {"unavailable", "nan", "none"}:
        return None
    v = re.sub(r"^https?://(dx\.)?doi\.org/", "", v)
    v = re.sub(r"^doi:", "", v)
    return v if v.startswith("10.") else None


def slug(d):
    return re.sub(r"[^a-z0-9._-]", "_", d)


def fetch(doi, tries=4):
    url = OC + urllib.parse.quote(doi, safe="/.")
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "scholarly-record-ontology/0.1 (mailto:fabio@thetesseractacademy.com)"})
            with urllib.request.urlopen(req, timeout=180) as r:
                if r.status in (301, 302):
                    return None
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if attempt == tries - 1:
                print(f"  give up {doi}: {e}", file=sys.stderr, flush=True)
                return None
            time.sleep(min(2 ** attempt, 20))
    return None


def main():
    os.makedirs(DERIVED, exist_ok=True)
    os.makedirs(GRAPH, exist_ok=True)

    # retraction dates
    rw = pd.read_csv(os.path.join(RAW, "retraction_watch.csv"), dtype=str, keep_default_na=False)
    rw = rw[rw["RetractionNature"] == "Retraction"]
    rw["doi"] = rw["OriginalPaperDOI"].map(norm_doi)
    rw["dt"] = pd.to_datetime(rw["RetractionDate"], format="%m/%d/%Y %H:%M", errors="coerce")
    retr_date = {}
    journal = {}
    for r in rw.itertuples(index=False):
        if isinstance(r.doi, str) and pd.notna(r.dt):
            retr_date[r.doi] = r.dt.date().isoformat()
            journal[r.doi] = r.Journal

    # rank by citation count from the OpenAlex harvest
    cited = {}
    with open(os.path.join(RAW, "openalex_retracted.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            try:
                it = json.loads(line)
            except json.JSONDecodeError:
                continue
            d = norm_doi(it.get("doi"))
            if d and d in retr_date:
                cited[d] = it.get("cited_by_count") or 0
    targets = [d for d, _ in sorted(cited.items(), key=lambda x: -x[1])[:TOP_N]]
    print(f"retracted works with a date: {len(retr_date)}")
    print(f"ranked by citations       : {len(cited)}")
    print(f"fetching citations for top: {len(targets)}", flush=True)

    results = {}
    done = [0]

    def work(d):
        c = fetch(d)
        done[0] += 1
        if done[0] % 50 == 0:
            print(f"  {done[0]}/{len(targets)}", flush=True)
        return d, c

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for d, c in ex.map(work, targets):
            if c:
                results[d] = c

    # grade
    out = gzip.open(os.path.join(GRAPH, "sro-propagation.nt.gz"), "wt", encoding="utf-8")
    n_t = 0

    def t(s, p, o):
        nonlocal n_t
        out.write(f"<{s}> <{p}> {o} .\n")
        n_t += 1

    severe = caution = unknown = 0
    per_work = []
    citing_severe = set()
    for d, cits in results.items():
        rd = retr_date[d]
        s = c = u = 0
        for row in cits:
            citing = norm_doi(row.get("citing"))
            created = (row.get("creation") or "")[:10]
            if not citing:
                continue
            if len(created) >= 7:
                grade = "signal-severe" if created[:7] > rd[:7] else "signal-caution"
            else:
                grade = None
                u += 1
            ev = BASE + f"citation/{slug(citing)}/{slug(d)}"
            t(ev, RDFT, f"<{SRO}CitationEvent>")
            t(ev, SRO + "citingWork", f"<{BASE}work/{slug(citing)}>")
            t(ev, SRO + "citedWork", f"<{BASE}work/{slug(d)}>")
            if created[:4].isdigit():
                t(ev, SRO + "citationYear", f'"{created[:4]}"^^<{XSD}gYear>')
            if grade:
                t(ev, SRO + "postDatesAssertion",
                  f'"{"true" if grade=="signal-severe" else "false"}"^^<{XSD}boolean>')
                sig = BASE + f"signal/{slug(citing)}/{slug(d)}"
                t(sig, RDFT, f"<{SRO}PropagationSignal>")
                t(sig, SRO + "signalGrade", f"<{SRO}{grade}>")
                t(sig, SRO + "signalDerivedFrom",
                  f"<{BASE}assertion/rw/{slug(d)}/retracted/{rd}>")
                t(f"{BASE}work/{slug(citing)}", SRO + "hasSignal", f"<{sig}>")
                if grade == "signal-severe":
                    s += 1
                    citing_severe.add(citing)
                else:
                    c += 1
        severe += s
        caution += c
        unknown += u
        per_work.append({"doi": d, "journal": journal.get(d), "retraction_date": rd,
                         "citations": len(cits), "severe": s, "caution": c})
    out.close()

    per_work.sort(key=lambda x: -x["severe"])
    summary = {
        "works_requested": len(targets),
        "works_with_citation_data": len(results),
        "citations_examined": severe + caution + unknown,
        "severe_signals": severe,
        "caution_signals": caution,
        "undated_citations": unknown,
        "severe_pct_of_dated": round(100 * severe / (severe + caution), 2) if (severe + caution) else None,
        "distinct_citing_works_carrying_severe": len(citing_severe),
        "triples": n_t,
        "worst_works": per_work[:20],
    }
    with open(os.path.join(DERIVED, "propagation.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)

    for k in ["works_with_citation_data", "citations_examined", "severe_signals",
              "caution_signals", "severe_pct_of_dated",
              "distinct_citing_works_carrying_severe", "triples"]:
        print(f"{k:42} {summary[k]}")
    print("\n--- works generating the most severe signals ---")
    for r in per_work[:12]:
        print(f"  {r['severe']:>5} severe / {r['citations']:>5} cites  {r['doi']}  ({r['retraction_date']}, {str(r['journal'])[:40]})")


if __name__ == "__main__":
    main()
