#!/usr/bin/env python3
"""Three-register comparison of the retracted scholarly record.

Registers compared:
  RW  Retraction Watch (via Crossref Labs, CC0)
  CR  Crossref `update-to` assertions
  OA  OpenAlex is_retracted flag

Everything printed here is computed from the harvested files. No estimates.

Output: data/derived/findings.json  + human-readable stdout report
"""
import json
import os
import re
from collections import Counter, defaultdict

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
DERIVED = os.path.join(HERE, "..", "data", "derived")

RETRACTIVE = {"retraction", "retration", "partial_retraction", "withdrawal", "removal"}
EOC = {"expression_of_concern"}

F = {}


def norm_doi(v):
    if not isinstance(v, str):
        return None
    v = v.strip().lower()
    if not v or v in {"unavailable", "nan", "none"}:
        return None
    v = re.sub(r"^https?://(dx\.)?doi\.org/", "", v)
    v = re.sub(r"^doi:", "", v)
    return v if v.startswith("10.") else None


def is_relx(pub):
    """Elsevier imprints = RELX's STM division."""
    if not isinstance(pub, str):
        return False
    p = pub.lower()
    return "elsevier" in p or "cell press" in p


def jload(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue


def main():
    os.makedirs(DERIVED, exist_ok=True)

    # ---------- Retraction Watch ----------
    rw = pd.read_csv(os.path.join(RAW, "retraction_watch.csv"), dtype=str, keep_default_na=False)
    rw["doi_n"] = rw["OriginalPaperDOI"].map(norm_doi)
    # US-format dates with time component. An implicit parse silently drops these.
    rw["retr_dt"] = pd.to_datetime(rw["RetractionDate"], format="%m/%d/%Y %H:%M", errors="coerce")
    rw["orig_dt"] = pd.to_datetime(rw["OriginalPaperDate"], format="%m/%d/%Y %H:%M", errors="coerce")

    F["rw_records"] = int(len(rw))
    F["rw_nature_counts"] = {k: int(v) for k, v in rw["RetractionNature"].value_counts().items()}
    F["rw_date_parse_failures"] = int(rw["retr_dt"].isna().sum())
    F["rw_records_without_original_doi"] = int(rw["doi_n"].isna().sum())

    rw_retr = rw[rw["RetractionNature"] == "Retraction"]
    RW_R = set(rw_retr["doi_n"].dropna())
    RW_EOC = set(rw[rw["RetractionNature"] == "Expression of concern"]["doi_n"].dropna())
    RW_REINSTATED = set(rw[rw["RetractionNature"] == "Reinstatement"]["doi_n"].dropna())
    F["rw_unique_retracted_dois"] = len(RW_R)
    F["rw_unique_eoc_dois"] = len(RW_EOC)
    F["rw_unique_reinstated_dois"] = len(RW_REINSTATED)
    # A DOI carrying both a retraction and a reinstatement record = contested status
    F["rw_retracted_and_reinstated"] = len(RW_R & RW_REINSTATED)

    # retraction date earlier than original publication date = impossible ordering
    both = rw_retr.dropna(subset=["retr_dt", "orig_dt"])
    F["rw_retraction_before_publication"] = int((both["retr_dt"] < both["orig_dt"]).sum())
    F["rw_retraction_before_publication_examples"] = [
        {"doi": r["doi_n"], "journal": r["Journal"], "publisher": r["Publisher"],
         "original": str(r["orig_dt"].date()), "retracted": str(r["retr_dt"].date())}
        for _, r in both[both["retr_dt"] < both["orig_dt"]].head(8).iterrows() if r["doi_n"]
    ]

    # ---------- Crossref ----------
    cr_type_counts = Counter()
    cr_self_ref = Counter()
    cr_targets = defaultdict(set)      # update_type -> set of target DOIs
    cr_asserted_pub = {}               # target doi -> asserting publisher
    cr_source_counts = Counter()
    cr_notice_dois = set()
    for it in jload(os.path.join(RAW, "crossref_updates.jsonl")):
        asserting = norm_doi(it.get("DOI"))
        pub = it.get("publisher")
        cr_notice_dois.add(asserting)
        for u in it.get("update-to") or []:
            utype = (u.get("type") or "").strip()
            target = norm_doi(u.get("DOI"))
            if not target:
                continue
            cr_type_counts[utype] += 1
            cr_source_counts[(u.get("source") or "").strip()] += 1
            cr_targets[utype].add(target)
            if asserting == target:
                cr_self_ref[utype] += 1
            if utype in RETRACTIVE:
                cr_asserted_pub.setdefault(target, pub)

    F["crossref_update_type_counts"] = dict(cr_type_counts.most_common())
    F["crossref_update_source_counts"] = dict(cr_source_counts.most_common())
    F["crossref_distinct_update_types"] = len(cr_type_counts)
    CR_R = set().union(*[cr_targets[t] for t in RETRACTIVE if t in cr_targets]) if cr_targets else set()
    CR_EOC = set().union(*[cr_targets[t] for t in EOC if t in cr_targets]) if any(t in cr_targets for t in EOC) else set()
    F["crossref_unique_retracted_dois"] = len(CR_R)
    F["crossref_unique_eoc_dois"] = len(CR_EOC)

    tot_retr_assert = sum(cr_type_counts[t] for t in RETRACTIVE if t in cr_type_counts)
    tot_self = sum(cr_self_ref[t] for t in RETRACTIVE if t in cr_self_ref)
    F["crossref_retractive_assertions"] = tot_retr_assert
    F["crossref_self_referential_assertions"] = tot_self
    F["crossref_self_referential_pct"] = round(100 * tot_self / tot_retr_assert, 2) if tot_retr_assert else None

    # ---------- OpenAlex ----------
    OA_R = set()
    oa_pub = {}
    oa_cites = {}
    oa_year = {}
    oa_counts_by_year = {}
    oa_no_doi = 0
    for it in jload(os.path.join(RAW, "openalex_retracted.jsonl")):
        d = norm_doi(it.get("doi"))
        if not d:
            oa_no_doi += 1
            continue
        OA_R.add(d)
        oa_cites[d] = it.get("cited_by_count") or 0
        oa_year[d] = it.get("publication_year")
        oa_counts_by_year[d] = it.get("counts_by_year") or []
        loc = (it.get("primary_location") or {}).get("source") or {}
        oa_pub[d] = loc.get("host_organization_name") or loc.get("display_name")
    F["openalex_retracted_records"] = len(OA_R) + oa_no_doi
    F["openalex_retracted_with_doi"] = len(OA_R)
    F["openalex_retracted_without_doi"] = oa_no_doi

    # ---------- Three-way agreement ----------
    F["venn"] = {
        "rw_only": len(RW_R - CR_R - OA_R),
        "cr_only": len(CR_R - RW_R - OA_R),
        "oa_only": len(OA_R - RW_R - CR_R),
        "rw_cr_not_oa": len((RW_R & CR_R) - OA_R),
        "rw_oa_not_cr": len((RW_R & OA_R) - CR_R),
        "cr_oa_not_rw": len((CR_R & OA_R) - RW_R),
        "all_three": len(RW_R & CR_R & OA_R),
        "union": len(RW_R | CR_R | OA_R),
    }
    F["agreement_pct_of_union"] = round(100 * F["venn"]["all_three"] / F["venn"]["union"], 2) if F["venn"]["union"] else None

    # ---------- Silent failures (probe) ----------
    probe_path = os.path.join(RAW, "openalex_rw_probe.jsonl")
    if os.path.exists(probe_path):
        known_unflagged = []
        absent = 0
        found = 0
        probed = 0
        for it in jload(probe_path):
            d = it.get("_probe_doi")
            probed += 1
            if not it.get("_found"):
                absent += 1
                continue
            found += 1
            if not it.get("is_retracted") and d in RW_R:
                known_unflagged.append({
                    "doi": d,
                    "cited_by_count": it.get("cited_by_count") or 0,
                    "publisher": ((it.get("primary_location") or {}).get("source") or {}).get("host_organization_name"),
                })
        F["probe_total"] = probed
        F["probe_found_in_openalex"] = found
        F["probe_absent_from_openalex"] = absent
        F["silent_failures"] = len(known_unflagged)
        F["silent_failure_pct_of_found"] = round(100 * len(known_unflagged) / found, 2) if found else None
        F["silent_failure_citations_total"] = sum(x["cited_by_count"] for x in known_unflagged)
        top = sorted(known_unflagged, key=lambda x: -x["cited_by_count"])[:15]
        F["silent_failure_top_cited"] = top
        pubc = Counter(x["publisher"] or "UNKNOWN" for x in known_unflagged)
        F["silent_failure_by_publisher"] = dict(pubc.most_common(20))
        F["silent_failure_relx"] = sum(v for k, v in pubc.items() if is_relx(k))

    # ---------- Post-retraction citation ----------
    retr_year = {}
    for _, r in rw_retr.iterrows():
        d, dt = r["doi_n"], r["retr_dt"]
        if d and pd.notna(dt):
            retr_year[d] = dt.year
    post = 0
    pre = 0
    works_cited_after = 0
    per_pub_post = Counter()
    worst = []
    for d, y in retr_year.items():
        cby = oa_counts_by_year.get(d)
        if not cby:
            continue
        after = sum(c.get("cited_by_count", 0) for c in cby if c.get("year") and c["year"] > y)
        before = sum(c.get("cited_by_count", 0) for c in cby if c.get("year") and c["year"] <= y)
        post += after
        pre += before
        if after > 0:
            works_cited_after += 1
            per_pub_post[oa_pub.get(d) or "UNKNOWN"] += after
            worst.append({"doi": d, "retraction_year": y, "citations_after": after,
                          "publisher": oa_pub.get(d)})
    F["post_retraction_citations_total"] = post
    F["pre_retraction_citations_in_window"] = pre
    F["works_cited_after_retraction"] = works_cited_after
    F["works_with_citation_timeline"] = sum(1 for d in retr_year if oa_counts_by_year.get(d))
    F["post_retraction_by_publisher"] = dict(per_pub_post.most_common(15))
    F["post_retraction_worst_offenders"] = sorted(worst, key=lambda x: -x["citations_after"])[:15]
    F["post_retraction_relx_citations"] = sum(v for k, v in per_pub_post.items() if is_relx(k))

    # ---------- RELX / Elsevier specific ----------
    rw_pub = rw_retr["Publisher"].map(lambda p: "RELX/Elsevier" if is_relx(p) else "other")
    F["rw_retractions_relx"] = int((rw_pub == "RELX/Elsevier").sum())
    F["rw_retractions_total_records"] = int(len(rw_retr))
    F["rw_relx_pct"] = round(100 * F["rw_retractions_relx"] / len(rw_retr), 2)
    relx_dois = set(rw_retr[rw_pub == "RELX/Elsevier"]["doi_n"].dropna())
    F["relx_retracted_dois"] = len(relx_dois)
    F["relx_flagged_in_openalex"] = len(relx_dois & OA_R)
    F["relx_flagged_in_crossref"] = len(relx_dois & CR_R)
    F["relx_openalex_coverage_pct"] = round(100 * len(relx_dois & OA_R) / len(relx_dois), 2) if relx_dois else None
    F["relx_crossref_coverage_pct"] = round(100 * len(relx_dois & CR_R) / len(relx_dois), 2) if relx_dois else None

    # per-publisher propagation league table (RW publishers with >=200 retracted DOIs)
    table = []
    for pub, grp in rw_retr.groupby("Publisher"):
        ds = set(grp["doi_n"].dropna())
        if len(ds) < 200:
            continue
        table.append({
            "publisher": pub,
            "retracted_dois": len(ds),
            "in_crossref": len(ds & CR_R),
            "in_openalex": len(ds & OA_R),
            "crossref_pct": round(100 * len(ds & CR_R) / len(ds), 1),
            "openalex_pct": round(100 * len(ds & OA_R) / len(ds), 1),
        })
    F["publisher_propagation_table"] = sorted(table, key=lambda x: x["crossref_pct"])

    with open(os.path.join(DERIVED, "findings.json"), "w", encoding="utf-8") as fh:
        json.dump(F, fh, indent=2, ensure_ascii=False, default=str)

    # ---------- report ----------
    print("=" * 72)
    print("THREE-REGISTER COMPARISON OF THE RETRACTED SCHOLARLY RECORD")
    print("=" * 72)
    for k in ["rw_records", "rw_nature_counts", "rw_date_parse_failures",
              "rw_unique_retracted_dois", "rw_retracted_and_reinstated",
              "rw_retraction_before_publication",
              "crossref_distinct_update_types", "crossref_unique_retracted_dois",
              "crossref_self_referential_pct",
              "openalex_retracted_with_doi", "openalex_retracted_without_doi",
              "venn", "agreement_pct_of_union",
              "probe_found_in_openalex", "probe_absent_from_openalex",
              "silent_failures", "silent_failure_pct_of_found", "silent_failure_citations_total",
              "post_retraction_citations_total", "works_cited_after_retraction",
              "rw_retractions_relx", "rw_relx_pct",
              "relx_openalex_coverage_pct", "relx_crossref_coverage_pct"]:
        if k in F:
            print(f"{k:40} {F[k]}")
    print("\n--- publisher propagation league table (worst Crossref coverage first) ---")
    for r in F["publisher_propagation_table"][:20]:
        print(f"  {r['publisher'][:44]:46} n={r['retracted_dois']:>6}  CR={r['crossref_pct']:>5}%  OA={r['openalex_pct']:>5}%")
    print("\n--- crossref update-type vocabulary (as harvested) ---")
    for k, v in list(F["crossref_update_type_counts"].items()):
        print(f"  {v:>8}  {k}")


if __name__ == "__main__":
    main()
