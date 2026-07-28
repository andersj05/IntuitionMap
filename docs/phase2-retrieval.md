# Phase 2 retrieval and measurement

**Status:** complete; G2 not passed

**Run date:** 2026-07-28

**Spend:** 0 paid requests, 0 tokens, $0

## Scope

Phase 2 tests whether transparent local retrieval methods can recover evidence
sessions on a public memory benchmark. It also strengthens the IntuitionMap
evaluation contract before any private content is imported.

This evidence supports only C2 generic retrieval capability. LongMemEval does
not contain this user's thoughts, personal link verdicts, explicit links, or
known-invalid relationships, so it cannot establish personal associative
fidelity.

The preregistered cards are:

- [`EXP-P2-001`](../configs/experiments/EXP-P2-001-cheap-retrieval.yaml)
- [`EXP-P2-002`](../configs/experiments/EXP-P2-002-local-embedding-hybrid.yaml)

## Implemented controls

All implementations are deterministic, dependency-free, and local:

- stable random ranking keyed by seed, query ID, and candidate ID;
- most-recent ranking;
- TF-IDF cosine;
- BM25 with frozen `k1=1.2` and `b=0.75`;
- explicit-link-first ranking where source-authored links exist;
- a 512-dimensional signed hash projection of tokens and adjacent token
  bigrams;
- reciprocal-rank fusion of BM25, the hash projection, and recency with
  `k=60`.

The hash projection is an embedding interface and reproducible local feature
baseline. It is not a neural or semantic embedding model, and its scores are
not described as semantic understanding.

Prediction records distinguish raw ranking scores from calibrated confidence.
These methods emit `confidence: null`, `abstained: false`, and
`status: uncalibrated`; a raw BM25, cosine, or fusion score is never presented
as a probability.

## Benchmark protocol

The input is the pinned cleaned LongMemEval-S artifact:

- upstream revision:
  `98d7416c24c778c2fee6e6f3006e7a073259d48f`;
- artifact SHA-256:
  `d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442`;
- 500 native queries, of which 470 are retrieval-scored;
- 30 query IDs ending in `_abs` excluded as required by the
  [official retrieval protocol](https://github.com/xiaowu0162/LongMemEval#memory-retrieval).

Rankers receive only the question and sessions in its supplied native history.
They never receive the answer, `has_answer` flags, or evidence-session IDs.
Ranking uses unique adapter IDs while preserving native session IDs.

### Timestamp audit and protocol correction

The official benchmark says the question is answered after all supplied
interaction sessions. The cleaned artifact nevertheless contains:

- 22,389 sessions dated before `question_date`;
- 3 sessions dated exactly at `question_date`;
- 1,475 sessions dated after `question_date`;
- 75 evidence sessions among the after-date cases.

The native history envelope therefore determines benchmark availability.
These timestamps are retained and counted; none is rewritten or dropped.
Strict capture-time chronology remains mandatory for IntuitionMap datasets.

An initial run that interpreted `question_date` as the availability cutoff
stopped at query 301 before producing results. That run is invalid and retained
in the result ledger. The protocol was corrected from the official source
before the scored run.

## Results

Macro evidence-session results over the 470 retrieval-scored queries:

| Method | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR | P50 latency |
|---|---:|---:|---:|---:|---:|---:|
| Stable random | 0.0239 | 0.0801 | 0.1299 | 0.2240 | 0.1523 | 0.29 ms |
| Most recent | 0.0273 | 0.0841 | 0.1518 | 0.2866 | 0.1596 | 0.14 ms |
| TF-IDF | 0.4878 | 0.7973 | 0.8644 | 0.9214 | 0.8421 | 55.53 ms |
| BM25 | 0.5573 | 0.8620 | 0.9112 | 0.9488 | 0.9119 | 12.61 ms |
| Hash projection | 0.2606 | 0.4602 | 0.5475 | 0.6635 | 0.5341 | 77.84 ms |
| RRF hybrid | 0.2876 | 0.5588 | 0.7133 | 0.8354 | 0.6427 | 90.76 ms |

BM25 improved recall@10 over the strongest preregistered cheaper control,
TF-IDF, by `+0.02745`. The paired 2,000-resample query bootstrap 95% interval
was `[+0.01450, +0.04262]`. The interval excludes zero, but the effect is below
both the five-point absolute and ten-percent relative practical thresholds.
`EXP-P2-001` is therefore a no-go.

The RRF hybrid changed recall@10 relative to BM25 by `-0.11348`, with a 95%
interval of `[-0.13731, -0.09092]`. This is a clear negative result, so the
hash channel and hybrid are not promoted.

On the tiny smoke correctness probe, every lexical/hash method exposed `0.50`
known-invalid predictions per judged query at `k=5`; recency exposed `0.3333`.
This probe is too small for a quality claim, but neither preregistered
comparison violated its relative invalid-exposure tolerance.

The ignored full result is
`runs/phase2-longmemeval-s.json`, 6,659,710 bytes, SHA-256
`a5d310a5ce2b47538c7b586c7dcd51242fa83e53a15845bdc37b5c356a41f68f`.
It contains per-query metrics, question-type subgroups, top-10 rankings,
latencies, timestamp audits, spend records, and both paired comparisons.

## Error screening

The BM25 smoke run produced five deterministic screening rows at `k=5`:

- two missed associative links, both also flagged `OVERLY_SAFE` because the
  relevant pair has no retained lexical overlap;
- three known-invalid exposures whose targets triggered the smoke-only
  `GENERIC_HUB` heuristic.

The candidate pools are so small that the hub heuristic over-flags old nodes.
These are triage codes requiring human adjudication, not causal explanations.
Unlabeled pairs remain unknown and do not appear as errors.

## Decision

G2 is **not passed**. Per the preregistered stop rule:

- TF-IDF remains the accepted cheap generic floor;
- BM25 remains a useful observed comparator but is not promoted by this gate;
- the hash projection and RRF hybrid remain negative diagnostic controls;
- no paid or larger model experiment is justified by these results.

Phase 3 may proceed because its purpose is to build privacy, consent,
annotation, export, and deletion safeguards. No personal quality claim may
advance until protected user judgments exist and a later preregistered system
passes G2/G4 on an appropriate source.

## Reproduction

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m intuition_map_eval.longmemeval_benchmark `
  --artifact datasets/external/longmemeval/98d7416c24c778c2fee6e6f3006e7a073259d48f/longmemeval_s_cleaned.json `
  --smoke-dataset datasets/smoke `
  --output runs/phase2-longmemeval-s.json
```

Neither command makes an API request.
