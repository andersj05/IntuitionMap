# IntuitionMap decision and result log

**Policy:** append-only. Supersede a decision with a new entry; do not silently
rewrite history. Null, negative, and invalid results remain recorded.

Status vocabulary:

- `accepted`
- `rejected`
- `deferred`
- `superseded`
- `result-pass`
- `result-fail`
- `result-mixed`
- `result-invalid`

## Decision template

```text
## DEC-NNNN — Short title
Date:
Status:
Scope:

Context:
Decision:
Evidence:
Alternatives considered:
Consequences:
Revisit when:
```

## DEC-0001 — Use an observable target, not an undefined intuition claim

**Date:** 2026-07-28
**Status:** `accepted`
**Scope:** research program

**Context:** “Human intuition” does not supply an operational label or
falsifiable endpoint by itself.

**Decision:** The first target is personalized, temporal, directed link
prediction: for each new thought, rank earlier thoughts that the user would
label `essential` or `valid`, predict relation/verdict confidence, and abstain
when evidence is weak.

**Evidence:** The evaluation contract already represents immutable thoughts,
directed temporal judgments, and unknown unlabeled pairs. Kahneman and Klein
also make feedback quality and environmental regularity prerequisites for
trustworthy intuitive expertise.

**Alternatives considered:** claim to reproduce intuition directly; use an
attractive graph or LLM explanation as the target.

**Consequences:** Claims advance through C1–C5. Synthetic/public evidence can
establish capability but not personal associative fidelity.

**Revisit when:** protected personal evaluation shows a stable phenomenon that
the current verdict/relation schema cannot represent.

## DEC-0002 — Evaluation and baselines precede the product’s linking model

**Date:** 2026-07-28
**Status:** `accepted`
**Scope:** implementation order

**Context:** A sophisticated linker can create plausible graphs without
recovering user-important connections.

**Decision:** Maintain the evaluation harness, chronological protocol,
auditable artifacts, cheap controls, and advancement gates before adding
opaque models or optimizing the visualization.

**Evidence:** Candidate generation bounds every later classifier; long-context
models can miss supplied evidence; recent graph-memory results are on generic
QA and require matched controls.

**Alternatives considered:** build the full UI and graph first; judge link
quality by demos; train a large model first.

**Consequences:** The UI scaffold may evolve independently, but a visual graph
does not count as research evidence. Every nontrivial run needs an experiment
card.

**Revisit when:** never for research claims; product prototyping can proceed in
parallel without bypassing gates.

## DEC-0003 — Public and synthetic data are capability evidence only

**Date:** 2026-07-28
**Status:** `accepted`
**Scope:** claims and evaluation

**Context:** No reviewed public source contains this user’s chronological
thoughts and directed `essential`/`valid`/`invalid`/`uncertain` judgments.

**Decision:** Keep smoke, public benchmark, weak private, private gold, and
future multi-user results as separate tiers. Never pool their headline metrics.

**Evidence:** LongMemEval tests temporal chat memory, LaMP/PersonalLLM test
personalization proxies, and ConceptNet/ATOMIC test generic relations; none
measures the user’s latent directed associations.

**Alternatives considered:** pretrain on public association graphs and label
the result “personal intuition”; use LLM-generated labels as personal gold.

**Consequences:** C3 requires protected user judgments; C5 requires consented
multi-user replication.

**Revisit when:** only if a public dataset with suitable consent, provenance,
chronology, and direct personal judgments is located and independently audited.

## DEC-0004 — Register exact terms before acquiring external data

**Date:** 2026-07-28
**Status:** `accepted`
**Scope:** data governance

**Context:** Repository code licenses do not necessarily govern benchmark data
or its upstream sources.

**Decision:** No external artifact may be acquired until
[the dataset registry](dataset-registry.md) records the exact version, source,
terms, allowed use, retrieval method/date, and checksum. External raw data stays
under ignored `datasets/external/`.

**Evidence:** LaMP explicitly delegates to underlying-source terms; LongMemEval
has a clear MIT repository license but insufficiently clear separately scoped
dataset terms on the reviewed release page; PersonalLLM license metadata
conflicts with an earlier planning note.

**Alternatives considered:** assume the repository license covers every file;
vendor benchmark data into Git.

**Consequences:** Phase 1 starts with terms/version resolution and acquisition
scripts, not ad hoc downloads.

**Revisit when:** never as a control; individual dataset status changes when its
card is complete.

## DEC-0005 — Captured thoughts are immutable; model memory is derived

**Date:** 2026-07-28
**Status:** `accepted`
**Scope:** storage and provenance

**Context:** Systems such as A-MEM update historical memory context, keywords,
or tags as new information arrives. That can improve retrieval while obscuring
what the user actually wrote and when.

**Decision:** Preserve source captures and timestamps exactly. Store summaries,
tags, embeddings, proposed links, evolved context, and contradictions as
separate versioned artifacts with model/config/time provenance.

**Evidence:** The current evaluation contract depends on point-in-time
reconstruction and has a zero-tolerance `PROVENANCE_INVERSION` failure.

**Alternatives considered:** overwrite an old note with the model’s latest
interpretation; present generated summaries as user-authored memory.

**Consequences:** Derived artifacts can be regenerated, compared, deleted, and
audited without corrupting source history.

**Revisit when:** never for source content; a user-authored edit becomes a new
version/event rather than a silent overwrite.

## DEC-0006 — Unlabeled is unknown, not invalid

**Date:** 2026-07-28
**Status:** `accepted`; naive-negative alternative `rejected`
**Scope:** labels and training

**Context:** Most prior-thought pairs will never be reviewed. Model proposals
also influence which pairs become visible.

**Decision:** Only an explicit `invalid` verdict is a negative. Preserve
`uncertain` and missing pairs separately, log exposure/proposal source and
sampling probability, and use positive-unlabeled or exposure-aware methods
where appropriate.

**Evidence:** PU learning requires explicit assumptions about how positives are
labeled; recommender evidence shows missing-not-at-random exposure biases
learning and evaluation.

**Alternatives considered:** sample arbitrary unlabeled pairs and train them as
negatives; pool discovery and proposal judgments without an exposure feature.

**Consequences:** Data volume appears smaller but the scientific target remains
valid. Controlled random candidates and hard explicit invalids are necessary.

**Revisit when:** an annotation protocol establishes exhaustive judgments for a
clearly bounded candidate pool.

## DEC-0007 — Defer personal-data collection until the protected path exists

**Date:** 2026-07-28
**Status:** `accepted`
**Scope:** privacy and execution order

**Context:** The user expects to contribute personal data, but importing it now
would precede consent, local-storage, redaction, export, deletion, exposure
logging, and protected-test controls.

**Decision:** Do not request or import personal content during Phases 0–2.
Implement and test the Phase 3 private-data path first. Then ask the user for an
explicitly scoped pilot, describing fields, purpose, service boundaries,
retention, deletion, and labeling burden.

**Evidence:** Raw thoughts are sensitive and central claims require a test set
that model selection cannot contaminate.

**Alternatives considered:** collect notes immediately and design governance
later; send all notes to a hosted model by default.

**Consequences:** Current work uses only repository-authored smoke data and
public metadata. `datasets/private/` remains ignored.

**Revisit when:** Phase 3’s consent, local storage, redaction, export, deletion,
annotation, and chronological test controls have passing tests.

## DEC-0008 — Defer foundation-model training, GNNs, and learned memory policy

**Date:** 2026-07-28
**Status:** `deferred`; starting with these approaches `rejected`
**Scope:** model complexity

**Context:** Recent work reports gains from graph retrieval and RL memory
policies, but those methods are costly and can hide simpler retrieval effects.

**Decision:** Follow B0–B7 in order. Begin with random/recency/lexical controls,
one fixed local embedding model, deterministic fusion, directed reranking, and
a small personal head. Test graph traversal only at matched budgets; consider
RL/GNN/PEFT only after data-volume and learning-curve evidence.

**Evidence:** HippoRAG attributes many errors to extraction; AgeMem trains on
controlled HotpotQA trajectories; Associa adds graph construction and iterative
model calls. None establishes personal-intuition fidelity.

**Alternatives considered:** train a foundation model; build a temporal GNN
before labels exist; copy an end-to-end agentic memory stack.

**Consequences:** A complex system advances only when one controlled change
beats the strongest cheaper comparator.

**Revisit when:** G4/G5 evidence and an experiment card show that remaining
errors cannot be addressed by cheaper models.

## DEC-0009 — Paid inference is opt-in, capped, and unnecessary for G0

**Date:** 2026-07-28
**Status:** `accepted`
**Scope:** spend

**Context:** The user explicitly requires careful API-token and dollar control.

**Decision:** Phase 0 runs offline. Any later paid request requires the config
gate, CLI gate, worst-case preflight within `max_cost_usd`, per-request ledger,
zero automatic paid retries, exact model/pricing snapshot, and content-addressed
caching.

**Evidence:** The current harness implements the two-gate budget ledger and
records zero-cost usage for offline runs.

**Alternatives considered:** allow an agent to choose a hosted model or retry
automatically; use the API for smoke tests.

**Consequences:** No live adapter will be added until a preregistered experiment
needs it. The default evaluation remains deterministic and free.

**Revisit when:** an offline baseline is frozen and a paid experiment has a
specific decision, practical effect, and budget.

## DEC-0010 — Keep the Phase 1 public portfolio minimal and unresolved

**Date:** 2026-07-28
**Status:** `deferred`
**Scope:** dataset selection

**Context:** The plan needs orthogonal temporal-memory, sparse-personalization,
and generic-relation evidence, but acquiring every candidate increases cost,
terms risk, and false confidence.

**Decision:** Do not select or acquire a Phase 1 dataset in Phase 0. Resolve
LongMemEval data terms; select exactly one of LaMP/PersonalLLM and one of
ConceptNet/ATOMIC 2020 through experiment cards. ATOMIC is the provisional
relation preference because it is narrower and explicitly directed, but that is
not approval.

**Evidence:** Dataset roles and unresolved terms are recorded in
[the registry](dataset-registry.md).

**Alternatives considered:** download the whole candidate matrix; combine all
public sources into a pretraining mixture.

**Consequences:** Phase 1 acquisition remains small, auditable, and reversible.
Negative transfer can later be measured one source at a time.

**Revisit when:** G0 passes and the Phase 1 experiment cards are ready.

## DEC-0011 — Canonicalize text before provenance hashing

**Date:** 2026-07-28
**Status:** `accepted`
**Scope:** reproducibility

**Context:** The first clean-copy validation showed that raw-byte SHA-256 values
for logically identical JSON/JSONL/config text changed when physical newlines
were LF versus CRLF.

**Decision:** Canonicalize physical text newlines to LF before computing dataset
and config provenance hashes. Retain raw artifact hashes for binary artifacts
when those are introduced. Enforce LF for repository text through
`.gitattributes`.

**Evidence:** Before the fix, the working tree and a fresh archive produced
different dataset fingerprints while containing logically identical records.
After the fix, an LF/CRLF regression test and two-run isolated validation pass.

**Alternatives considered:** accept platform-dependent fingerprints; rely only
on developer Git settings; normalize every file in place at runtime.

**Consequences:** A semantic text change still changes the hash, while checkout
newline style does not. The hash method must be recorded beside data-card file
hashes.

**Revisit when:** non-text dataset/config artifacts are added or the fingerprint
schema is versioned.

## DEC-0012 — Select a three-source Phase 1 portfolio

**Date:** 2026-07-28
**Status:** `accepted`; supersedes the deferred selection in DEC-0010
**Scope:** public data

**Context:** G0 passed, so the project needed the smallest public portfolio that
tests temporal memory, sparse personalization, and directed relation handling.

**Decision:** Select the pinned LongMemEval oracle artifact, PersonalLLM test
split, and ATOMIC 2020 February 2021 release. Defer LaMP and ConceptNet because
they add source/license complexity without adding an orthogonal Phase 1
capability. Keep LoCoMo, SWOW, OpenAlex, WikiLinkGraphs, PersonaLens, and remote
association sets deferred for the reasons in the registry.

**Evidence:** `EXP-P1-001`, the exact manifests under `configs/data/`, and
[the Phase 1 adapter validation](public-data-adapters.md).

**Alternatives considered:** acquire every candidate; choose LaMP plus
ConceptNet; skip public component checks and move directly to private data.

**Consequences:** The portfolio is under 37 MB and has separate native tasks.
PersonalLLM remains local-evaluation-only because its card does not fully
enumerate the terms of every upstream prompt source. None of the three sources
can support C3 or stronger claims.

**Revisit when:** a preregistered component experiment requires a capability the
selected source cannot test, or an upstream terms change invalidates an allowed
use.

## DEC-0013 — Preserve native anomalies instead of silently cleaning them

**Date:** 2026-07-28
**Status:** `accepted`
**Scope:** data provenance

**Context:** Fixture tests assumed LongMemEval answers were strings and ATOMIC
triples had three non-empty fields. Full-artifact validation falsified both
assumptions.

**Decision:** Preserve LongMemEval answers as native `str | int`. Preserve the
16 ATOMIC training rows with empty tails and mark them
`is_complete=False`. Any later filter must be explicit, counted, and recorded
in the experiment card.

**Evidence:** Full parsing found 32 integer LongMemEval answers and 16 empty
ATOMIC train tails, with no empty tails in dev or test.

**Alternatives considered:** coerce integers to strings; silently drop
incomplete triples; repair tails with model-generated text.

**Consequences:** Native counts and source defects remain auditable. Downstream
models cannot accidentally treat a fabricated cleanup as upstream ground truth.

**Revisit when:** an official corrected release is registered as a distinct
artifact and compared without overwriting this version.

## Result ledger

Use one row for every completed, null, failed, or invalid run. Link to the
experiment card and immutable artifact. A pass on smoke data is C1 evidence
only.

| ID | Date | Experiment/card | Status | Primary result | Cost | Decision / limitation | Artifact |
|---|---|---|---|---|---:|---|---|
| VAL-0001 | 2026-07-28 | [Phase 0 clean-environment validation](validation-record.md) | `result-pass` | 10 tests pass; two-run stable predictions/metrics/config/usage; zero paid calls | $0 | G0/C1 passes only; initial newline-dependent fingerprint defect was fixed and retained in the record. | Temporary isolated runs; stable hashes recorded in validation record |
| ACQ-P1-001A | 2026-07-28 | [`EXP-P1-001`](../configs/experiments/EXP-P1-001-data-readiness.yaml) | `invalid-run` | ATOMIC download rejected before promotion because a rounded webpage size was 2,529 bytes too high | $0 | Corrected from immutable mirror metadata; no unverified file retained. | No artifact promoted; failure retained in experiment result |
| VAL-P1-001 | 2026-07-28 | [`EXP-P1-001`](../configs/experiments/EXP-P1-001-data-readiness.yaml) | `result-pass` | Six registered files verified; 500 LongMemEval, 1,000 PersonalLLM, and 1,331,113 ATOMIC native records parsed; 20 tests pass | $0 | G1 passes only for the scoped local benchmark uses; C3–C5 remain unsupported. | Ignored `datasets/external/`; hashes in registry/manifests |

No model-quality experiment has yet produced a null or negative result.
Rejected approaches above are design decisions, not retroactively labeled
experiments.
