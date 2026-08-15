# Scholarly Record Ontology (SRO)

**An ontology and open dataset for the integrity status of the scholarly record, built to measure how badly the registers of that record disagree with each other.**

Legal publishing solved this problem in 1873. Frank Shepard, a salesman for a
Chicago legal publisher, began printing gummed labels, "Adhesive Annotations",
listing every later case that cited an earlier one, with one-letter codes marking
whether it had been overruled, criticised, modified or applied. That idea became
the citator: look up an authority, and the system tells you whether it still
stands. A lawyer who cites overturned authority has committed malpractice, and
the tooling makes that hard to do by accident.

Science has no citator. It has registers, and the registers do not agree.

The sharpest way to see the gap is that **one company owns both sides of it**.
Reed Elsevier, now RELX, acquired Shepard's in 1996 and took full ownership in
1998; it also owns Elsevier, the largest publisher of scientific literature, and
Scopus. The corporate group that operates the most rigorous citation-integrity
system ever built for law publishes a scientific record in which a retraction
notice for a *Nature* paper is itself recorded as retracted research.

This repository contains the ontology, the reproducible pipeline, and the
measurements.

---

## The headline results

All figures below were computed on **15 August 2026** from live sources by the
scripts in `scripts/`. Every number is regenerable. Provisional figures are
marked, and the reasons are in [BUILD_REPORT.md](BUILD_REPORT.md).

### 1. Crossref and Retraction Watch disagree about 27.6% of the retracted record

Crossref **acquired the Retraction Watch database in September 2023** and
publishes both. They are two datasets from one organisation. They still disagree.

| | DOIs |
|---|---|
| Asserted retracted by Retraction Watch | 60,247 |
| Asserted retracted by Crossref `update-to` | 78,907 |
| Asserted by **both** | 58,449 |
| Asserted by **at least one** | 80,705 |
| **Agreement (intersection / union)** | **72.42%** |
| In Retraction Watch, absent from Crossref | 1,798 (2.98% of RW) |
| In Crossref, absent from Retraction Watch | 20,458 (25.93% of Crossref) |

This comparison uses complete harvests of both sources and is not affected by
the OpenAlex shortfall described in the build report.

### 2. OpenAlex marks retraction notices as retracted research

A retraction notice is the document announcing that a paper has been withdrawn.
It is a valid, standing part of the record. OpenAlex flags tens of thousands of
them as retracted work:

- **64.2%** of Retraction Watch notice DOIs carry `is_retracted: true` in OpenAlex
- **25,681** notice DOIs that are *only* notices (never themselves a retracted paper) are flagged retracted
- **76.5%** of the DOIs OpenAlex uniquely calls retracted are notice DOIs

The most legible example: **[10.1038/s41586-023-06774-2](https://doi.org/10.1038/s41586-023-06774-2)**,
"Retraction Note: Evidence of near-ambient superconductivity in a N-doped lutetium
hydride", the *Nature* retraction note for one of the most scrutinised physics
papers of the decade. OpenAlex records the retraction note itself as retracted.

The consequence is not academic. Anything filtering `is_retracted:true` (an
integrity dashboard, a bibliometric study, a retrieval-augmented language model)
receives the corrective apparatus of science mixed in with the corrupted
literature, and cannot tell them apart.

### 3. The corrective vocabulary is uncontrolled

Crossref's `update-type` is the field the scholarly record uses to say what kind
of correction occurred. Across a complete harvest of **420,657** corrective
records, it takes **19 distinct values**, including:

| Value | Count | What it is |
|---|---|---|
| `retration` | 1 | misspelling of "retraction" |
| `retracion` | 1 | a *different* misspelling of "retraction" |
| `Retraction` | 3 | case variant, distinct from `retraction` |
| `expression-of-concern` | 3 | hyphenated variant of `expression_of_concern` |
| `68818` | 1 | a bare integer |
| `err` | 212 | abbreviation coexisting with `erratum` (139,755), `corrigendum` (8,944) and `corrected` (54) |

Every one is checkable. The misspelling `retration` belongs to
**[10.1016/j.cie.2010.04.003](https://doi.org/10.1016/j.cie.2010.04.003)**,
published by Elsevier BV, whose title literally begins "RETRACTED:". The human-readable
title says retracted; the machine-readable status is misspelled, so every query
filtering on `update-type:retraction` silently misses it. The integer `68818`
belongs to [10.3892/etm.2024.12720](https://doi.org/10.3892/etm.2024.12720)
(Spandidos Publications).

### 4. A quarter of retraction notices have no independent identity

**25.73%** of retractive assertions in Crossref register the notice against the
*same DOI* as the work it retracts. The notice is therefore not a separate
object: it cannot be cited, linked to, or counted on its own. SRO records this
explicitly rather than silently collapsing it (`sro:isSelfReferential`).

### 5. Retracted work keeps being cited

**291,177** citations to retracted works occurred in years after the retraction
date, across **35,261** distinct retracted works. This is a **lower bound**, see
the build report for why.

### 6. A null result, stated plainly

I expected to find that OpenAlex frequently holds a record for a retracted paper
without flagging it. It does not. Of 18,705 Retraction Watch DOIs probed and
found in OpenAlex, only **18 (0.1%)** were unflagged. Where OpenAlex has the
paper, it almost always knows. The failure is in the opposite direction: it
flags too much, and flags the wrong objects. This hypothesis was wrong and is
reported rather than buried.

---

## Why an ontology, and what it does differently

The existing scholarly vocabularies model retraction as a settled fact about a
work. I checked, rather than assumed. The files are fetched and grepped in the
build report:

- **CiTO** has `cito:retracts` and `cito:isRetractedBy`
- **FaBiO** has `fabio:Retraction`, `fabio:RetractionNotice`, `fabio:hasRetractionDate`
- **PSO** has `pso:retracted-from-publication`

None of them can express any of the following, all of which occur at scale in
real data:

| Real condition | Modelled by SPAR? |
|---|---|
| Expression of concern | **No**, the string does not occur in FaBiO, CiTO, PSO, PRO, SCoRO or DEO |
| Reinstatement of a retracted work | **No**, retraction is treated as terminal |
| Partial retraction | **No** |
| Removal (distinct from retraction) | **No** |
| Two registers asserting different statuses | **No**, status is a property of the work |
| A register holding the record and staying silent | **No** |
| A signal propagating to citing works | **No** |

SRO's central commitment: **retraction status is not a property of a work. It is
a dated claim by a named register.** Every claim is reified as an
`sro:IntegrityAssertion` attributed to an `sro:Register`, with the register's raw
status string retained verbatim, because normalising `retration` to `retraction`
destroys the evidence that the vocabulary is broken.

On top of that sit two things the scholarly graph has never had: first-class
vocabulary for **disagreement between registers** (`sro:RegisterDisagreement`,
including `sro:silentRegister`, because silence is a position), and a
citator-style **propagation layer** (`sro:PropagationSignal`) that grades a
citing work by the status of what it cites and by whether the citation
post-dates the assertion.

---

## Contents

```
ontology/sro-core.ttl        The ontology. 224 triples, 10 classes, 13 object
                             properties, 8 datatype properties, 19 individuals.
shapes/sro-shapes.ttl        SHACL in three layers: structural, value, coherence.
queries/README.md            Six worked SPARQL queries.
scripts/01..05               The pipeline, from live fetch to RDF.
data/graph/sro-instances.nt.gz  2,740,005 triples: 119,327 works, 57,943
                             corrective notices, 58,390 recorded disagreements.
data/graph/sro-example.ttl   Readable subgraph for review.
data/derived/findings.json   Every computed figure in this README.
BUILD_REPORT.md              What was fetched, what was computed, what could not
                             be obtained, and every caveat.
```

### Reproducing

```bash
pip install pandas rdflib pyshacl
python3 scripts/01_fetch_crossref_updates.py       # ~420k records
python3 scripts/02_fetch_openalex_retracted.py     # metered, see build report
python3 scripts/03_probe_openalex_for_rw_dois.py   # resumable
python3 scripts/04_analyse_registers.py            # findings.json
python3 scripts/05_build_graph.py                  # the RDF graph
```

Raw data is not committed: it is 502 MB and fully regenerable by the scripts
above. Retraction Watch is fetched from Crossref Labs, which publishes it openly
following the September 2023 acquisition.

### Validation

`pyshacl` reports **non-conformance, by design**. The shapes are diagnostic: the
remaining violations on the sample graph are 57 self-referential notices and 18
corrective notices asserted as retracted research. Those are the findings, not
defects in the data model.

---

## Licence

Ontology, shapes, queries and code: **MIT**. Documentation and derived findings:
**CC BY 4.0**. Source data belongs to Crossref, Retraction Watch and OpenAlex
under their own terms.

## Who built this and why

Built by **Fabio Rovai** at **The Tesseract Academy** (Kampakis and Co Ltd), as
part of a programme of open ontologies for domains where identifier governance
quietly fails, previously in [investment fund data](https://github.com/fabio-rovai/investment-fund-ontology)
and [insurance and reinsurance registers](https://github.com/fabio-rovai/insurance-register-ontology).
The pattern repeats across every sector examined so far: the register everyone
trusts disagrees with the register next to it, and nothing in the data model can
say so.

If you work on research integrity, scholarly infrastructure or knowledge graphs
and want the underlying data, a walkthrough, or the analysis run against your own
corpus: **fabio@thetesseractacademy.com**.

Corrections are welcome and will be credited. If a number here is wrong, open an
issue with the DOI and I will recheck it against source.
