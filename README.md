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

- **94.5%** of Retraction Watch notice DOIs carry `is_retracted: true` in OpenAlex (53,734 of 56,848)
- **93.0%** of DOIs that are *only* notices, never themselves a retracted paper, are flagged retracted (40,430 of 43,489)
- **74.5%** of the DOIs OpenAlex uniquely calls retracted are notice DOIs

The most legible example: **[10.1038/s41586-023-06774-2](https://doi.org/10.1038/s41586-023-06774-2)**,
"Retraction Note: Evidence of near-ambient superconductivity in a N-doped lutetium
hydride", the *Nature* retraction note for one of the most scrutinised physics
papers of the decade. OpenAlex records the retraction note itself as retracted.

The consequence is not academic. Anything filtering `is_retracted:true` (an
integrity dashboard, a bibliometric study, a retrieval-augmented language model)
receives the corrective apparatus of science mixed in with the corrupted
literature, and cannot tell them apart.

**The control test.** It would be unfair to conclude from Retraction Watch's own
notice column that OpenAlex is uniquely at fault, so I added a fourth register
that identifies notices independently. Europe PMC carries two distinct MEDLINE
publication types, "Retracted Publication" for the withdrawn paper and
"Retraction of Publication" for the notice. Taking Europe PMC's 19,803 notice
DOIs and asking each register what it says about them:

| Register | Notice DOIs it treats as retracted research |
|---|---|
| **OpenAlex** | **19,001 (95.95%)** |
| Crossref | 181 (0.91%) |
| Retraction Watch | 70 (0.35%) |
| Europe PMC itself | 64 (0.32%) |

Two independent measurements, one against Retraction Watch's notice column
(94.5%) and one against Europe PMC's publication types (95.95%), agree. This is
not a partial defect. OpenAlex flags essentially every retraction notice it holds
as retracted research.

Three registers keep the categories apart. One does not. Preserving the
distinction is plainly achievable in production, which is what makes this a
design defect rather than an inherent difficulty.

### 2b. Four registers, and only 19.24% agreement

With Europe PMC added, 137,243 DOIs are asserted retracted by at least one of the
four registers. Only **26,407 (19.24%)** are asserted by all four. **43.09%** rest
on a single register's say-so and would vanish from the record if you happened to
consult a different one.

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

### 5. Retracted work keeps being cited, and nothing warns anyone

**291,177** citations to retracted works occurred in years after the retraction
date, across **35,261** distinct retracted works. This is a **lower bound**, see
the build report for why.

To show what a citator would actually do with that, the propagation layer is
populated for the 400 most-cited retracted works using citation edges from
OpenCitations. Of 176,623 citations examined across 391 works with data:

| | |
|---|---|
| Citations post-dating the retraction (`severe`) | **43,683** |
| Citations pre-dating it (`caution`) | 105,485 |
| Severe as a share of dated citations | **29.28%** |
| Distinct citing works that would carry a red flag | **42,784** |

The works generating the most severe signals are not obscure:

| Retracted work | Retracted | Citations after |
|---|---|---|
| [10.1056/nejmoa1200303](https://doi.org/10.1056/nejmoa1200303) PREDIMED Mediterranean diet trial, *NEJM* | 2018-06-13 | 1,251 |
| [10.1016/s0140-6736(97)11096-0](https://doi.org/10.1016/s0140-6736(97)11096-0) Wakefield, *Lancet*, retracted for falsification | 2010-02-06 | **1,171** |
| [10.1126/science.1097243](https://doi.org/10.1126/science.1097243) Visfatin, *Science* | 2007-10-26 | 1,120 |
| [10.1056/nejmoa2007621](https://doi.org/10.1056/nejmoa2007621) Surgisphere COVID-19 paper, *NEJM* | 2020-06-04 | 833 |

The second row is the paper that launched the modern anti-vaccination movement,
retracted in 2010 for data falsification. It has been cited 1,171 times since,
and not one of those citations carries a machine-readable warning, because no
layer of the open scholarly record emits one.

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
ontology/sro-core.ttl        The ontology. 228 triples, 10 classes, 13 object
                             properties, 8 datatype properties, 20 individuals.
shapes/sro-shapes.ttl        SHACL in three layers: structural, value, coherence.
queries/README.md            Six worked SPARQL queries.
scripts/01..08               The pipeline, from live fetch to RDF.
data/graph/sro-instances.nt.gz   3,192,090 triples: 142,648 works, 60,637
                             corrective notices, 77,936 recorded disagreements,
                             across four registers.
data/graph/sro-propagation.nt.gz 1,450,797 triples: citation events and graded
                             propagation signals.
data/graph/sro-example.ttl   Readable subgraph for review.
data/derived/findings.json               Three-register figures.
data/derived/findings_four_register.json Europe PMC control test.
data/derived/propagation.json            Signal counts and worst cases.
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
python3 scripts/06_fetch_europepmc.py              # fourth register, unmetered
python3 scripts/07_build_propagation.py            # citator layer via OpenCitations
python3 scripts/08_analyse_four_registers.py       # the control test
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

## Related work

This sits alongside an existing quantitative literature rather than ahead of it.

Jonas Oppenlaender, *How Ten Publishers Retract Research*
([arXiv:2602.19197](https://arxiv.org/abs/2602.19197), February 2026), analyses
46,087 retractions in the Retraction Watch database and reports retraction rates
per publisher: Hindawi 320.02 per 10,000 published, IOS Press 283.77, PLoS 26.82,
IEEE 17.70, Springer Nature 9.06, and Elsevier lowest of the ten at 3.97. That
work measures **who retracts**. This project measures **whether the registers
agree that a retraction happened at all**, and whether anything propagates the
result. Different questions over the same corpus.

One of its findings bears directly on the ontology. Of 98 articles reinstated
following retraction, 86 were published in Elsevier journals. Reinstatement is a
real state occurring at measurable scale, and Retraction Watch records 160 such
cases. It is also a state no existing scholarly vocabulary can express: the
string does not occur in CiTO, FaBiO, PSO, PRO, SCoRO or DEO. A record that
models retraction as terminal will keep a warning against work that has been
cleared, which harms named authors.

A caution on reading Elsevier's low rate: it is equally consistent with a cleaner
corpus and with more conservative retraction practice, and pairing it with the
highest reinstatement share is what makes it interesting rather than settled. The
narrower claim from this project's own data is that where Elsevier does retract,
98.9% of those papers carry a corresponding Crossref assertion.

**Corporate reporting context.** The word "retract" does not appear anywhere in
the 252 pages of the RELX 2025 Annual Report, nor in its Form 20-F for the same
year, though research integrity is disclosed as a formal risk factor. The same
Annual Report places "Knowledge Graphs" in the grounding layer of its generative
AI diagram, on an axis labelled "Decreasing hallucination, irrelevant content,
non-attributable content (lack of citations)", and describes Elsevier products
using "hybrid search, knowledge graphs, ontologies". The mechanism is company
policy; the measurement of it is not published.

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
