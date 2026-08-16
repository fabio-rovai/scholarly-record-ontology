# Build report

Everything in this project was fetched live on **15 August 2026** and computed by
the scripts in `scripts/`. This document records exactly what was obtained, what
was not, and every caveat that qualifies a number in the README. It is written on
the assumption that a reader wants to attack the figures.

---

## 1. Sources fetched

| Source | Endpoint | Result | Status |
|---|---|---|---|
| Retraction Watch | `api.labs.crossref.org/data/retractionwatch?<email>` | 71,799 rows, 65.8 MB | **complete** |
| Crossref updates | `api.crossref.org/works?filter=update-type:<t>` cursor-paged, 13 types | 420,657 records, 175 MB | **complete** |
| OpenAlex retracted | `api.openalex.org/works?filter=is_retracted:true` cursor-paged | 107,200 of 134,094 (80.0%) | **incomplete, see §3** |
| OpenAlex DOI probe | batched `filter=doi:a\|b\|…` over Retraction Watch DOIs | 18,717 of 62,708 (29.8%) | **incomplete, see §3** |
| SPAR ontologies | `purl.org/spar/{cito,fabio,pso,pro,scoro,deo}` via content negotiation | 6 files, all parsed | **complete** |
| Europe PMC retracted | `ebi.ac.uk/europepmc/.../search?query=PUB_TYPE:"Retracted Publication"` | 33,893 records | **complete** |
| Europe PMC notices | same, `PUB_TYPE:"Retraction of Publication"` | 20,424 records | **complete** |
| OpenCitations citations | `opencitations.net/index/api/v1/citations/{doi}` | 391 of 400 works | **sampled, see §10** |

## 2. Retraction Watch composition

`RetractionNature` values as found, against the four values Crossref documents
("Retraction, Correction, Expression of concern, or Reinstatement"):

| Value | Records |
|---|---|
| Retraction | 66,287 |
| Expression of concern | 3,586 |
| Correction | 1,502 |
| *(empty)* | 264 |
| Reinstatement | 160 |

The 264 empty values are undocumented. They are excluded from all status-derived
figures rather than guessed at.

Dates in this file are US-format with a time component (`5/7/2026 0:00`). They
are parsed with an explicit `format="%m/%d/%Y %H:%M"`. **This matters**: a bare
`pd.to_datetime` call silently coerces a large fraction of them and inflates
every date-dependent figure. The same class of error was found and fixed in an
earlier build in this series against EIOPA data. 265 rows fail to parse and are
the 264 empty-nature rows plus one malformed row.

**Guarded null result:** zero records have a retraction date earlier than the
original publication date. The date fields are internally consistent.

## 3. OpenAlex metering, and a caveat that proved material

Partway through the first day's harvesting, OpenAlex began returning HTTP 429:

```json
{"error":"Rate limit exceeded",
 "message":"Insufficient budget. This request costs $0.0001 but you only have $0
  remaining. Resets at midnight UTC. Need more? Add funds at https://openalex.org/pricing",
 "dailyRemainingUsd":0, "creditsRemaining":0}
```

Response headers show `x-ratelimit-limit: 1000`, `x-ratelimit-limit-usd: 0.1`.
OpenAlex meters its API at roughly 1,000 requests, or $0.10, per day free. That
halted the harvest at 107,200 of 134,094 records. **It was resumed after the UTC
reset and is now complete at 134,113 records**, so no figure in the README
depends on partial OpenAlex data any longer.

I have not independently confirmed when this pricing began or its full terms; the
pricing page is a JavaScript application that did not render to a fetchable
document. The metering behaviour is directly observed and reproducible; the
policy history is **not verified**.

### The caveat was not merely formal

While the harvest was partial I warned that cursor order follows OpenAlex work
ID, which correlates with record creation, so the harvested subset was not a
random sample and percentages drawn from it should be treated as indicative
rather than exact. Completing the harvest showed that warning was correct and
that the effect was large.

Composition of the final 26,913 records, the segment missing on day one:

| | share |
|---|---|
| Retraction Watch **notice** DOIs | 56.6% |
| Europe PMC **notice** DOIs | 33.2% |
| Retraction Watch original-paper DOIs | 5.1% |

The tail of the cursor was dominated by notices. Consequently the headline
notice-conflation figure moved from a provisional 64.2% to a complete 94.5%, and
the Europe PMC control from 51.15% to 95.95%. Both moved in the same direction
and now agree with each other.

The lesson is worth stating plainly because it cuts against the usual instinct: a
partial harvest is not a small version of the whole. Where the sort key
correlates with how records were created, the missing slice can be the slice that
matters most. Had I published the 64.2% figure without the caveat, I would have
understated the defect by a third.

The DOI probe (`scripts/03`) remains partial and is resumed as budget allows. It
supports only the null result in README finding 6, where 22 of 20,779 probed DOIs
found in OpenAlex were unflagged (0.11%). That rate has been stable across two
sample sizes.

## 4. Post-retraction citations: why it is a lower bound

Computed from OpenAlex `counts_by_year`, summing citations in years strictly
after the Retraction Watch retraction year. Three reasons the true figure is
higher:

1. `counts_by_year` covers a limited recent window, not the full citation history.
2. Year granularity means citations in the retraction year itself are counted as
   pre-retraction, which is conservative.
3. The OpenAlex harvest is 80% complete.

Reported: 291,177 citations across 35,261 works. This figure did not change when
the OpenAlex harvest was completed, which is itself corroborating evidence: the
26,913 records added were overwhelmingly retraction notices rather than retracted
papers, and notices do not appear in Retraction Watch's original-paper column, so
they contribute nothing here.

## 5. A Crossref API caveat worth knowing

Facet counts and filter totals disagree substantially. `facet=update-type:*` over
`has-update:true` reports 27,652 for `retraction`, while
`filter=update-type:retraction` returns `total-results` of 74,571, and the
complete cursor harvest yields 117,521 retraction assertions. Crossref facets are
truncated at scale and must not be used for counting. All figures here come from
full cursor harvests, never facets.

## 6. Ontology alignment: every external IRI was verified before use

No alignment was asserted from memory. Each target was fetched and grepped, and
only `skos:closeMatch` / `skos:broadMatch` were used, never `owl:equivalentClass`
or `skos:exactMatch`, because the source vocabularies model a different thing
(a settled fact about a work) from what SRO models (a dated claim by a register).

Verified present:

- `http://purl.org/spar/fabio/Expression`, `.../RetractionNotice`
- `http://purl.org/spar/cito/cites`, `.../retracts`, `.../isRetractedBy`
- `http://purl.org/spar/pso/retracted-from-publication`

Note that CiTO declares `@prefix : <http://purl.org/spar/cito#>` but defines its
terms at `http://purl.org/spar/cito/` with a slash. Anyone constructing CiTO IRIs
from the prefix declaration will produce IRIs that do not exist.

Verified **absent** across `cito`, `fabio`, `pso`, `pro`, `scoro`, `deo`
(case-insensitive string search of the fetched Turtle):

- "expression of concern": 0 occurrences in any file
- "reinstat": 0 files
- "partial retraction": 0 files
- "removal": 0 files
- "propagat": 0 files

## 7. Validation

`ontology/sro-core.ttl` parses under rdflib: 224 triples, 10 classes, 13 object
properties, 8 datatype properties, 19 named individuals.

`pyshacl` 0.40.1 over the sample graph reports **non-conformance by design**,
with two remaining messages: 57 self-referential corrective notices (Warning,
rule R2) and 18 corrective notices asserted as retracted research (Violation,
rule R1). Both are the findings.

Two spurious violation classes were found during validation and fixed rather
than suppressed: assertion nodes were initially identified by
(register, work, status), which collapsed distinct dated claims into one node and
produced nodes carrying two `assertedDate` values. Assertion identity now
includes the date. This was a genuine modelling error caught by the shapes.

## 8. What could not be obtained

- The licence under which the Retraction Watch data is published. Crossref's
  documentation page states the acquisition and open availability but names no
  licence, and the GitLab distribution repository did not render a LICENSE file
  to inspection. Raw data is therefore **not committed** to this repository. Not
  verified: whether it is CC0.
- OpenAlex pricing history and terms (see §3).
- Any comparison against Scopus or Web of Science. Both are licensed products of
  RELX and Clarivate respectively, with no open API for this purpose. The
  measurements here are confined to open sources, which is itself the point: the
  open record is what most downstream tooling actually consumes.
- PubMed and Europe PMC as a fourth register. Feasible and free; not yet built.

## 10. Europe PMC and the propagation layer

**Europe PMC** was added specifically as a control. It is free, unmetered and
cursor-paged, and it carries separate MEDLINE publication types for the retracted
work and for the notice. It is therefore an independent source of notice DOIs,
which removes the objection that the OpenAlex category-error finding depends on
Retraction Watch's own notice column. Both harvests are complete. 631 of the
retracted records and 621 of the notice records carry no DOI and are excluded
from DOI-based comparisons.

Europe PMC's own two sets overlap on 64 DOIs (0.32% of notices), so it is not
itself free of the conflation, merely close to it. That figure is reported rather
than rounded to zero.

**The propagation layer** is a deliberate sample, not a census, and the sampling
is not neutral:

1. Only the **400 most-cited** retracted works were processed. Ranking uses
   OpenAlex `cited_by_count`, which comes from the 80%-complete harvest, so
   selection is biased toward works OpenAlex both knows and rates highly.
2. 391 of 400 returned citation data. The 9 failures were mostly
   `IncompleteRead` errors on the very largest citation lists, which means the
   losses are concentrated among the *most*-cited works. The severe-signal count
   is therefore an undercount, biased against the biggest cases.
3. 27,455 of 176,623 citations carry no usable creation date and are excluded
   from grading rather than guessed at.
4. Grading compares year and month only. A citation in the same month as the
   retraction is graded `caution`, which is the conservative direction.

Reported: 43,683 severe signals, 105,485 caution, 29.28% of dated citations
severe, 42,784 distinct citing works that would carry a red flag.

## 11. Known limitations

- DOI matching is exact after normalisation (lower-cased, resolver prefix and
  `doi:` stripped). Registrant-side DOI variance is not reconciled.
- "Publisher" is taken as the string each register reports. Imprint structures
  are not resolved to corporate parents beyond a documented Elsevier/Cell Press
  match used for the RELX-specific figures.
- The propagation layer (`sro:PropagationSignal`) is specified in the ontology and
  SHACL but not yet populated at scale; doing so requires a citation edge source
  such as OpenCitations, which is the next build step.
