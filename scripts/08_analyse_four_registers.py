#!/usr/bin/env python3
"""Add Europe PMC as a fourth register, and use it as the control case.

Europe PMC carries two distinct MEDLINE publication types:

    "Retracted Publication"      the withdrawn paper
    "Retraction of Publication"  the notice announcing the withdrawal

That is precisely the distinction OpenAlex collapses into one boolean. Europe
PMC therefore lets us test whether preserving the distinction is achievable in a
production register (it is) and gives an independent list of notice DOIs against
which the OpenAlex category error can be re-measured without relying on
Retraction Watch's own notice column.

Output: data/derived/findings_four_register.json
"""
import json
import os
import re

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
DERIVED = os.path.join(HERE, "..", "data", "derived")

RETRACTIVE = {"retraction", "retration", "retracion", "Retraction",
              "partial_retraction", "withdrawal", "removal"}


def norm_doi(v):
    if not isinstance(v, str):
        return None
    v = v.strip().lower()
    if not v or v in {"unavailable", "nan", "none"}:
        return None
    v = re.sub(r"^https?://(dx\.)?doi\.org/", "", v)
    v = re.sub(r"^doi:", "", v)
    return v if v.startswith("10.") else None


def jl(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue


def main():
    F = {}

    # ---- Europe PMC ----
    epmc_retracted, epmc_notices = set(), set()
    epmc_r_total = epmc_n_total = 0
    for it in jl(os.path.join(RAW, "europepmc_retracted.jsonl")):
        epmc_r_total += 1
        d = norm_doi(it.get("doi"))
        if d:
            epmc_retracted.add(d)
    for it in jl(os.path.join(RAW, "europepmc_notices.jsonl")):
        epmc_n_total += 1
        d = norm_doi(it.get("doi"))
        if d:
            epmc_notices.add(d)
    F["epmc_retracted_records"] = epmc_r_total
    F["epmc_notice_records"] = epmc_n_total
    F["epmc_retracted_with_doi"] = len(epmc_retracted)
    F["epmc_notices_with_doi"] = len(epmc_notices)

    # Does Europe PMC itself conflate the two categories?
    overlap = epmc_retracted & epmc_notices
    F["epmc_selfconflation_overlap"] = len(overlap)
    F["epmc_selfconflation_pct_of_notices"] = round(100 * len(overlap) / len(epmc_notices), 2) if epmc_notices else None

    # ---- other registers ----
    rw = pd.read_csv(os.path.join(RAW, "retraction_watch.csv"), dtype=str, keep_default_na=False)
    rwr = rw[rw["RetractionNature"] == "Retraction"]
    RW = set(rwr["OriginalPaperDOI"].map(norm_doi).dropna())
    RW_NOTICE = set(rwr["RetractionDOI"].map(norm_doi).dropna())

    CR, CR_NOTICE = set(), set()
    for it in jl(os.path.join(RAW, "crossref_updates.jsonl")):
        a = norm_doi(it.get("DOI"))
        for u in it.get("update-to") or []:
            if (u.get("type") or "").strip() in RETRACTIVE:
                t = norm_doi(u.get("DOI"))
                if t:
                    CR.add(t)
                    if a and a != t:
                        CR_NOTICE.add(a)

    OA = set()
    for it in jl(os.path.join(RAW, "openalex_retracted.jsonl")):
        d = norm_doi(it.get("doi"))
        if d:
            OA.add(d)

    F["register_sizes"] = {"retraction_watch": len(RW), "crossref": len(CR),
                           "openalex": len(OA), "europepmc": len(epmc_retracted)}

    # ---- four-way coverage of Europe PMC's retracted set ----
    F["epmc_also_in"] = {
        "retraction_watch": len(epmc_retracted & RW),
        "crossref": len(epmc_retracted & CR),
        "openalex": len(epmc_retracted & OA),
        "none_of_the_three": len(epmc_retracted - RW - CR - OA),
    }
    F["epmc_only_pct"] = round(100 * len(epmc_retracted - RW - CR - OA) / len(epmc_retracted), 2)

    # ---- THE CONTROL TEST ----
    # Europe PMC independently identifies which DOIs are notices. How many of
    # those does OpenAlex flag as retracted research?
    en_flagged = epmc_notices & OA
    F["control_epmc_notices_flagged_by_openalex"] = len(en_flagged)
    F["control_epmc_notices_flagged_pct"] = round(100 * len(en_flagged) / len(epmc_notices), 2) if epmc_notices else None
    # and how many does Crossref treat as retracted works (rather than as the asserting record)?
    F["control_epmc_notices_asserted_retracted_by_crossref"] = len(epmc_notices & CR)
    F["control_epmc_notices_pct_crossref"] = round(100 * len(epmc_notices & CR) / len(epmc_notices), 2) if epmc_notices else None
    # Retraction Watch treats notices as a separate column, so this should be low
    F["control_epmc_notices_in_rw_original_column"] = len(epmc_notices & RW)
    F["control_epmc_notices_pct_rw"] = round(100 * len(epmc_notices & RW) / len(epmc_notices), 2) if epmc_notices else None

    # ---- union across all four ----
    union = RW | CR | OA | epmc_retracted
    allfour = RW & CR & OA & epmc_retracted
    F["four_register_union"] = len(union)
    F["four_register_agreement"] = len(allfour)
    F["four_register_agreement_pct"] = round(100 * len(allfour) / len(union), 2)
    F["asserted_by_exactly_one"] = sum(
        1 for d in union
        if sum([d in RW, d in CR, d in OA, d in epmc_retracted]) == 1)
    F["asserted_by_exactly_one_pct"] = round(100 * F["asserted_by_exactly_one"] / len(union), 2)

    with open(os.path.join(DERIVED, "findings_four_register.json"), "w", encoding="utf-8") as fh:
        json.dump(F, fh, indent=2, ensure_ascii=False)

    print("=" * 70)
    print("FOUR-REGISTER COMPARISON (Europe PMC added as control)")
    print("=" * 70)
    for k, v in F.items():
        print(f"{k:46} {v}")


if __name__ == "__main__":
    main()
