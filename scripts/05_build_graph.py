#!/usr/bin/env python3
"""Emit the SRO instance graph from the three harvested registers.

Design note: findings are computed set-based (pandas/sets), never by SPARQL
anti-joins over the full graph. rdflib cannot execute NOT EXISTS / MINUS at this
scale in acceptable time, so the graph is the publishable artifact and the
pipeline is the computation.

Outputs:
  data/graph/sro-instances.nt.gz   full instance graph (N-Triples, gzipped)
  data/graph/sro-example.ttl       readable subgraph for review
"""
import gzip
import json
import os
import re
from collections import defaultdict

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
GRAPH = os.path.join(HERE, "..", "data", "graph")

SRO = "https://ontology.tesseract.academy/sro/"
BASE = "https://ontology.tesseract.academy/sro/id/"
XSD = "http://www.w3.org/2001/XMLSchema#"
RDFT = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"

RETRACTIVE = {"retraction", "retration", "retracion", "Retraction",
              "partial_retraction", "withdrawal", "removal"}
STATUS_MAP = {
    "retraction": "retracted", "retration": "retracted", "retracion": "retracted",
    "Retraction": "retracted", "partial_retraction": "partially-retracted",
    "withdrawal": "withdrawn", "removal": "removed",
    "expression_of_concern": "expression-of-concern",
    "expression-of-concern": "expression-of-concern",
}


def norm_doi(v):
    if not isinstance(v, str):
        return None
    v = v.strip().lower()
    if not v or v in {"unavailable", "nan", "none"}:
        return None
    v = re.sub(r"^https?://(dx\.)?doi\.org/", "", v)
    v = re.sub(r"^doi:", "", v)
    return v if v.startswith("10.") else None


def slug(doi):
    return re.sub(r"[^a-z0-9._-]", "_", doi)


def esc(s):
    return (str(s).replace("\\", "\\\\").replace('"', '\\"')
            .replace("\n", "\\n").replace("\r", ""))


class Writer:
    def __init__(self, path):
        self.fh = gzip.open(path, "wt", encoding="utf-8")
        self.n = 0
        self.sample = []

    def t(self, s, p, o, keep=False):
        line = f"<{s}> <{p}> {o} .\n"
        self.fh.write(line)
        self.n += 1
        if keep and len(self.sample) < 4000:
            self.sample.append(line)

    def lit(self, v, dt=None):
        return f'"{esc(v)}"^^<{XSD}{dt}>' if dt else f'"{esc(v)}"'

    def close(self):
        self.fh.close()


def main():
    os.makedirs(GRAPH, exist_ok=True)
    w = Writer(os.path.join(GRAPH, "sro-instances.nt.gz"))

    works = set()
    notices = set()
    keep_doi = set()  # DOIs whose triples also go into the readable sample

    # ---------- Retraction Watch assertions ----------
    rw = pd.read_csv(os.path.join(RAW, "retraction_watch.csv"), dtype=str, keep_default_na=False)
    rw["orig"] = rw["OriginalPaperDOI"].map(norm_doi)
    rw["notice"] = rw["RetractionDOI"].map(norm_doi)
    rw["dt"] = pd.to_datetime(rw["RetractionDate"], format="%m/%d/%Y %H:%M", errors="coerce")
    rw = rw.rename(columns={"Record ID": "RecordID"})
    # pandas represents the None returned by norm_doi as NaN; normalise back
    rw["orig"] = rw["orig"].where(rw["orig"].notna(), None)
    rw["notice"] = rw["notice"].where(rw["notice"].notna(), None)
    nature_map = {"Retraction": "retracted", "Expression of concern": "expression-of-concern",
                  "Correction": "corrected", "Reinstatement": "reinstated"}

    rw_status = defaultdict(set)
    for i, r in enumerate(rw.itertuples(index=False)):
        d = r.orig
        if not isinstance(d, str):
            continue
        st = nature_map.get(r.RetractionNature)
        if not st:
            continue
        keep = len(keep_doi) < 60
        if keep:
            keep_doi.add(d)
        wu = BASE + "work/" + slug(d)
        if d not in works:
            works.add(d)
            w.t(wu, RDFT, f"<{SRO}ScholarlyWork>", keep)
            w.t(wu, SRO + "doi", w.lit(d), keep)
        dstr = str(r.dt.date()) if pd.notna(r.dt) else ""
        au = BASE + "assertion/rw/" + slug(d) + "/" + st + ("/" + dstr if dstr else "")
        w.t(au, RDFT, f"<{SRO}IntegrityAssertion>", keep)
        w.t(au, SRO + "aboutWork", f"<{wu}>", keep)
        w.t(au, SRO + "assertedBy", f"<{SRO}RetractionWatchRegister>", keep)
        w.t(au, SRO + "hasStatus", f"<{SRO}{st}>", keep)
        w.t(au, SRO + "rawStatusLabel", w.lit(r.RetractionNature), keep)
        w.t(au, SRO + "sourceRecordId", w.lit(r.RecordID), keep)
        if dstr:
            w.t(au, SRO + "assertedDate", w.lit(dstr, "date"), keep)
        if isinstance(r.notice, str):
            nu = BASE + "work/" + slug(r.notice)
            if r.notice not in notices:
                notices.add(r.notice)
                w.t(nu, RDFT, f"<{SRO}CorrectiveNotice>", keep)
                w.t(nu, SRO + "doi", w.lit(r.notice), keep)
            w.t(au, SRO + "evidencedByNotice", f"<{nu}>", keep)
            w.t(au, SRO + "isSelfReferential",
                w.lit("true" if r.notice == d else "false", "boolean"), keep)
        rw_status[d].add(st)

    # ---------- Crossref assertions ----------
    cr_status = defaultdict(set)
    cr_notice_dois = set()
    with open(os.path.join(RAW, "crossref_updates.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            try:
                it = json.loads(line)
            except json.JSONDecodeError:
                continue
            a = norm_doi(it.get("DOI"))
            if a:
                cr_notice_dois.add(a)
            for u in it.get("update-to") or []:
                raw = (u.get("type") or "").strip()
                st = STATUS_MAP.get(raw)
                if not st:
                    continue
                t = norm_doi(u.get("DOI"))
                if not t:
                    continue
                keep = t in keep_doi
                wu = BASE + "work/" + slug(t)
                if t not in works:
                    works.add(t)
                    w.t(wu, RDFT, f"<{SRO}ScholarlyWork>", keep)
                    w.t(wu, SRO + "doi", w.lit(t), keep)
                d8 = (u.get("updated") or {}).get("date-time", "")[:10]
                # An assertion is identified by register, work, status AND date:
                # the same register restating a status on a later date is a
                # distinct claim, not a duplicate of the first.
                au = (BASE + "assertion/cr/" + slug(a or t) + "/" + slug(t)
                      + "/" + st + ("/" + d8 if len(d8) == 10 else ""))
                w.t(au, RDFT, f"<{SRO}IntegrityAssertion>", keep)
                w.t(au, SRO + "aboutWork", f"<{wu}>", keep)
                w.t(au, SRO + "assertedBy", f"<{SRO}CrossrefRegister>", keep)
                w.t(au, SRO + "hasStatus", f"<{SRO}{st}>", keep)
                # raw label retained: the evidence that the vocabulary is uncontrolled
                w.t(au, SRO + "rawStatusLabel", w.lit(raw), keep)
                w.t(au, SRO + "isSelfReferential",
                    w.lit("true" if a == t else "false", "boolean"), keep)
                if len(d8) == 10:
                    w.t(au, SRO + "assertedDate", w.lit(d8, "date"), keep)
                cr_status[t].add(st)

    # ---------- OpenAlex assertions ----------
    oa_flagged = set()
    oa_path = os.path.join(RAW, "openalex_retracted.jsonl")
    with open(oa_path, encoding="utf-8") as fh:
        for line in fh:
            try:
                it = json.loads(line)
            except json.JSONDecodeError:
                continue
            d = norm_doi(it.get("doi"))
            if not d:
                continue
            oa_flagged.add(d)
            keep = d in keep_doi
            wu = BASE + "work/" + slug(d)
            if d not in works:
                works.add(d)
                w.t(wu, RDFT, f"<{SRO}ScholarlyWork>", keep)
                w.t(wu, SRO + "doi", w.lit(d), keep)
            au = BASE + "assertion/oa/" + slug(d) + "/retracted"
            w.t(au, RDFT, f"<{SRO}IntegrityAssertion>", keep)
            w.t(au, SRO + "aboutWork", f"<{wu}>", keep)
            w.t(au, SRO + "assertedBy", f"<{SRO}OpenAlexRegister>", keep)
            w.t(au, SRO + "hasStatus", f"<{SRO}retracted>", keep)
            w.t(au, SRO + "rawStatusLabel", w.lit("is_retracted=true"), keep)
            if it.get("publication_year"):
                w.t(wu, SRO + "publicationDate",
                    w.lit(f"{it['publication_year']}-01-01", "date"), keep)

    # ---------- Europe PMC assertions ----------
    epmc_flagged = set()
    for fname, cls in (("europepmc_retracted.jsonl", "ScholarlyWork"),
                       ("europepmc_notices.jsonl", "CorrectiveNotice")):
        path = os.path.join(RAW, fname)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    it = json.loads(line)
                except json.JSONDecodeError:
                    continue
                d = norm_doi(it.get("doi"))
                if not d:
                    continue
                keep = d in keep_doi
                wu = BASE + "work/" + slug(d)
                if cls == "CorrectiveNotice" and d not in notices:
                    notices.add(d)
                    w.t(wu, RDFT, f"<{SRO}CorrectiveNotice>", keep)
                    w.t(wu, SRO + "doi", w.lit(d), keep)
                elif cls == "ScholarlyWork":
                    epmc_flagged.add(d)
                    if d not in works:
                        works.add(d)
                        w.t(wu, RDFT, f"<{SRO}ScholarlyWork>", keep)
                        w.t(wu, SRO + "doi", w.lit(d), keep)
                    au = BASE + "assertion/epmc/" + slug(d) + "/retracted"
                    w.t(au, RDFT, f"<{SRO}IntegrityAssertion>", keep)
                    w.t(au, SRO + "aboutWork", f"<{wu}>", keep)
                    w.t(au, SRO + "assertedBy", f"<{SRO}EuropePMCRegister>", keep)
                    w.t(au, SRO + "hasStatus", f"<{SRO}retracted>", keep)
                    w.t(au, SRO + "rawStatusLabel", w.lit("Retracted Publication"), keep)

    # ---------- Disagreements (computed set-based) ----------
    rw_retr = {d for d, s in rw_status.items() if "retracted" in s}
    cr_retr = {d for d, s in cr_status.items() if "retracted" in s}
    n_dis = 0

    def disagree(doi, kind, asserting, silent):
        nonlocal n_dis
        n_dis += 1
        u = BASE + f"disagreement/{kind}/" + slug(doi)
        keep = doi in keep_doi
        w.t(u, RDFT, f"<{SRO}RegisterDisagreement>", keep)
        w.t(u, SRO + "concernsWork", f"<{BASE}work/{slug(doi)}>", keep)
        w.t(u, SRO + "hasDisagreementKind", f"<{SRO}{kind}>", keep)
        for a in asserting:
            w.t(u, SRO + "assertingRegister", f"<{SRO}{a}>", keep)
        for s in silent:
            w.t(u, SRO + "silentRegister", f"<{SRO}{s}>", keep)

    for d in (rw_retr | cr_retr) - oa_flagged:
        a = ([("RetractionWatchRegister")] if d in rw_retr else []) + \
            ([("CrossrefRegister")] if d in cr_retr else [])
        disagree(d, "silent-omission", a, ["OpenAlexRegister"])
    for d in rw_retr - cr_retr:
        disagree(d, "silent-omission", ["RetractionWatchRegister"], ["CrossrefRegister"])
    # a notice that is itself flagged retracted = category error, recorded as a conflict
    notice_flagged = (notices | cr_notice_dois) & oa_flagged
    for d in notice_flagged:
        disagree(d, "status-conflict", ["OpenAlexRegister"], [])

    w.close()

    with open(os.path.join(GRAPH, "sro-example.ttl"), "w", encoding="utf-8") as fh:
        fh.write(f"# Readable subgraph of the SRO instance graph.\n"
                 f"# Full graph: sro-instances.nt.gz ({w.n} triples)\n\n")
        for line in w.sample:
            fh.write(line)

    print(f"triples          : {w.n}")
    print(f"works            : {len(works)}")
    print(f"corrective notices: {len(notices)}")
    print(f"disagreements    : {n_dis}")
    print(f"notices flagged retracted by OpenAlex: {len(notice_flagged)}")
    print(f"wrote {GRAPH}/sro-instances.nt.gz and sro-example.ttl")


if __name__ == "__main__":
    main()
