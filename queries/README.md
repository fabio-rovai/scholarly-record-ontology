# SPARQL queries

Run against `data/graph/sro-instances.nt.gz` (decompress first) or the readable
subgraph `data/graph/sro-example.ttl`.

A warning carried over from earlier builds in this series: rdflib will not
execute `MINUS` / `NOT EXISTS` anti-joins over a graph of this size in
acceptable time. Q4 and Q5 below are written as the semantics the model
intends; the published figures are computed set-based in
`scripts/04_analyse_registers.py`. Treat the queries as the specification and
the pipeline as the implementation.

---

## Q1. Which registers assert a status for a given work, and do they agree?

```sparql
PREFIX sro: <https://ontology.tesseract.academy/sro/>
SELECT ?register ?status ?date ?raw WHERE {
  ?work sro:doi "10.1016/j.cie.2010.04.003" .
  ?a sro:aboutWork ?work ;
     sro:assertedBy ?register ;
     sro:hasStatus  ?status .
  OPTIONAL { ?a sro:assertedDate ?date }
  OPTIONAL { ?a sro:rawStatusLabel ?raw }
}
```

## Q2. The uncontrolled vocabulary, straight from the data

Every distinct raw status string a register actually published, with counts.
This is how the misspellings surface.

```sparql
PREFIX sro: <https://ontology.tesseract.academy/sro/>
SELECT ?raw (COUNT(*) AS ?n) WHERE {
  ?a sro:assertedBy sro:CrossrefRegister ;
     sro:rawStatusLabel ?raw .
} GROUP BY ?raw ORDER BY DESC(?n)
```

## Q3. Corrective notices with no independent identity

```sparql
PREFIX sro: <https://ontology.tesseract.academy/sro/>
SELECT (COUNT(DISTINCT ?a) AS ?selfReferential) WHERE {
  ?a a sro:IntegrityAssertion ;
     sro:isSelfReferential true .
}
```

## Q4. The category error: notices marked as retracted research

```sparql
PREFIX sro: <https://ontology.tesseract.academy/sro/>
SELECT ?doi WHERE {
  ?notice a sro:CorrectiveNotice ;
          sro:doi ?doi .
  ?a sro:aboutWork ?notice ;
     sro:hasStatus sro:retracted ;
     sro:assertedBy sro:OpenAlexRegister .
}
```

## Q5. Silent omissions: one register asserts, another holds the record and says nothing

```sparql
PREFIX sro: <https://ontology.tesseract.academy/sro/>
SELECT ?doi ?asserting ?silent WHERE {
  ?d a sro:RegisterDisagreement ;
     sro:hasDisagreementKind sro:silent-omission ;
     sro:concernsWork ?w ;
     sro:assertingRegister ?asserting ;
     sro:silentRegister ?silent .
  ?w sro:doi ?doi .
}
```

## Q6. Works whose status is contested rather than settled

```sparql
PREFIX sro: <https://ontology.tesseract.academy/sro/>
SELECT ?doi WHERE {
  ?w sro:doi ?doi .
  ?a1 sro:aboutWork ?w ; sro:hasStatus sro:retracted .
  ?a2 sro:aboutWork ?w ; sro:hasStatus sro:reinstated .
}
```
