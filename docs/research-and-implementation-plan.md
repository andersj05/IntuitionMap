# IntuitionMap Research and Implementation Plan

**Status:** Canonical execution plan
**Last updated:** 2026-07-28
**Audience:** Research and implementation agents working in this repository

## Executive decision

IntuitionMap should not begin by training a foundation model or by trying to
reproduce an undefined human faculty called "intuition." The first defensible
target is narrower and measurable:

> Given a newly captured thought and only the user's earlier history, rank the
> earlier thoughts that this user would judge to be essential or valid
> connections, identify the likely relationship, and abstain when evidence is
> weak.

This is a personalized, temporal, directed link-prediction problem over
thought-level objects. A transformer can still encode the language inside each
thought. The new machinery learns relationships *between thought
representations*: retrieval proposes candidates, a pairwise model judges a
directed connection, a user-specific component adapts those judgments, and a
graph retrieves useful neighborhoods.

No public dataset found so far directly contains chronological personal
thoughts with directed `essential`, `valid`, `invalid`, and `uncertain`
judgments. Public data can teach or test generic capabilities, but only
user-owned labels can establish that the system predicts this user's
associations. The program therefore uses:

1. public benchmarks for memory, personalization, commonsense relations, and
   temporal link-prediction;
2. synthetic data for software correctness and controlled failure tests;
3. weak supervision extracted from user-owned history;
4. a small, carefully protected personal gold set;
5. a future consented multi-user study only after the single-user system works.

The project advances only when a change beats a cheaper baseline on an
untouched chronological evaluation set, with uncertainty estimates and without
an unacceptable increase in invalid suggestions, cost, latency, or privacy
risk.

## 1. Scientific target

### 1.1 Operational definition

For a new thought \(q_t\), let \(H_{<t}\) be every thought available before its
capture time. For each candidate \(x_i \in H_{<t}\), the system estimates:

- a graded verdict: `essential`, `valid`, `invalid`, or `uncertain`;
- zero or more directed relation types;
- a calibrated confidence;
- evidence and provenance for why the connection was proposed.

The candidate ranker should maximize retrieval of essential and valid links in
a small review budget while minimizing exposure to known-invalid links.
Unlabeled pairs remain unknown; they are never silently converted into
negatives.

This operationalization does **not** claim to transfer subjective experience.
It tests whether a system can learn a useful approximation of the user's
observable associative judgments and whether that approximation improves later
reasoning.

### 1.2 Claim ladder

Claims must be earned in this order:

1. **Software correctness:** the pipeline is deterministic where expected,
   leak-free, reproducible, and correctly scored.
2. **Generic retrieval:** it retrieves semantically and temporally relevant
   memories on public and controlled data.
3. **Personal associative fidelity:** personal feedback improves prediction of
   this user's held-out judgments over the strongest generic system.
4. **Downstream utility:** the learned graph improves a real task such as
   resurfacing, synthesis, planning, or contradiction detection.
5. **Generalizable personal intuition modeling:** the effect replicates across
   consenting users and survives user-level holdout.

Synthetic data, LLM-generated labels, or an attractive graph cannot support
claims 3–5.

### 1.3 Non-goals for the first program

- Training an LLM from scratch.
- Claiming consciousness, felt intuition, or mind reading.
- Treating semantic similarity as a complete definition of intuition.
- Scraping public personal-note vaults without explicit permission and a
  compatible license.
- Treating clicks, co-occurrence, or missing labels as ground truth.
- Optimizing end-to-end generation before candidate retrieval is reliable.
- Using an LLM judge as the sole measure of human agreement or usefulness.

## 2. Research questions and falsifiable hypotheses

| ID | Research question | Initial hypothesis | Evidence needed |
|---|---|---|---|
| RQ1 | Can earlier essential links be recovered in a small candidate budget? | Hybrid lexical, embedding, and recency retrieval will beat any single channel. | Chronological essential recall at fixed `k`, invalid exposure, latency, and paired confidence interval. |
| RQ2 | Can a model distinguish a meaningful directed relationship from topical similarity? | A pairwise reranker with direction and relation supervision will improve graded ranking over embedding similarity. | Held-out ranking and relation metrics; explicit near-topic invalid examples. |
| RQ3 | Does personal feedback add signal beyond generic language knowledge? | A small user-specific ranker or adapter on frozen representations will beat the strongest generic model before full-model tuning is justified. | Untouched personal chronological test set and cold-start learning curve. |
| RQ4 | Is the learned mapping stable as the user changes? | Time-aware weighting and periodic recalibration will outperform a stationary profile after enough history exists. | Rolling-origin evaluation and drift analysis. |
| RQ5 | Does a graph add value over a flat memory store? | Graph traversal helps multi-hop retrieval and synthesis but not necessarily first-hop candidate recall. | Flat-versus-graph ablation at equal retrieval and model budgets. |
| RQ6 | Can the system find useful remote, contradictory, or structurally analogous links? | Diversity-aware retrieval can improve accepted novel links without causing hub saturation. | Controlled probes plus blinded human review of real suggestions. |
| RQ7 | Do better edge metrics improve an actual task? | Better essential recall should improve downstream usefulness only when provenance and precision remain acceptable. | Paired task evaluation, not edge metrics alone. |
| RQ8 | Can the system remain attributable, private, and reversible? | Immutable source capture, explicit provenance, local private data, and deletion tests can make the system auditable. | Safety audit, provenance tests, and successful deletion propagation. |

An experiment that cannot change a decision should not be run.

## 3. Literature-review workstream

The next research agent must perform a reproducible review before choosing a
novel architecture. The purpose is to extract mechanisms, assumptions,
evaluation designs, and negative results—not merely collect papers.

### 3.1 Search areas

1. Cognitive accounts of intuition: recognition-primed decision making,
   conditions for intuitive expertise, dual-process theories, spreading
   activation, associative learning, schema formation, and analogical
   transfer.
2. Computational memory: complementary learning systems, hippocampal indexing,
   episodic and semantic memory, consolidation, forgetting, and temporal
   context models.
3. LLM memory systems: retrieval, reflection, dynamic memory organization,
   learned write/read policies, graph memory, contradiction handling, and
   long-horizon evaluation.
4. Personalization: user embeddings, parameter-efficient adaptation,
   preference learning, meta-learning, cold-start behavior, continual learning,
   and privacy-preserving personalization.
5. Relational learning: link prediction, knowledge graphs, graph neural
   networks, hypergraphs, heterogeneous temporal graphs, and calibrated
   selective prediction.
6. Data-efficient learning: active learning, weak supervision, positive and
   unlabeled learning, pairwise ranking, hard-negative mining, and human label
   reliability.
7. Evaluation: chronological/off-policy evaluation, recommender-system
   exposure bias, selective labels, user studies, calibration, and
   human-in-the-loop systems.

### 3.2 Review protocol

- Search primary sources in ACL Anthology, ACM Digital Library, IEEE Xplore,
  OpenReview, proceedings sites, arXiv, and relevant cognitive-science
  journals. Record the search date and exact query.
- Use backward and forward citation chaining from the seed works below.
- Include a work only if it defines a mechanism, dataset, evaluation, or
  falsifiable claim relevant to at least one research question.
- Create `docs/literature-matrix.md` with one row per work:
  citation, year, definition of memory/intuition, mechanism, training signal,
  dataset, split, baselines, primary metric, result, limitation, available
  code/data, license, and relevance to an IntuitionMap experiment.
- Separate peer-reviewed evidence, preprints, benchmark papers, and product
  claims. Never copy a reported improvement without its baseline, dataset,
  metric, and evaluation conditions.
- Record failed replications and evidence against the preferred design in the
  same matrix.
- End the review with a mechanism comparison and a list of experiments that
  could distinguish competing explanations.

### 3.3 Seed literature

This list starts the review; it is not an assertion that these systems solve
personal intuition.

- [A-MEM: Agentic Memory for LLM Agents](https://arxiv.org/abs/2502.12110):
  dynamic, Zettelkasten-inspired note construction, linking, and memory
  evolution.
- [Bridging Intuitive Associations and Deliberate Recall
  (Associa)](https://aclanthology.org/2025.findings-acl.901/): event-centric
  graph memory, associative retrieval, and deliberate graph selection.
- [HippoRAG](https://arxiv.org/abs/2405.14831): knowledge-graph retrieval with
  Personalized PageRank, motivated by hippocampal indexing.
- [Generative Agents](https://arxiv.org/abs/2304.03442): recency, importance,
  relevance, and reflection over an episodic memory stream.
- [Agentic Memory: Learning Unified Long-Term and Short-Term Memory
  Management](https://arxiv.org/abs/2601.01885): learned memory-operation
  policies; evaluate carefully against simpler retrieval controls.
- [Conditions for Intuitive Expertise](https://doi.org/10.1037/a0016755):
  intuition should be expected to become reliable only in sufficiently regular
  environments with opportunities for feedback.

The review should also look for strong negative results: cases where graph
memory, reflection, personalization, or long-context models fail to outperform
simple retrieval when compute and information access are controlled.

## 4. Data strategy

### 4.1 Dataset fit and acquisition matrix

Licenses below are planning notes, not legal advice. The implementing agent must
record the exact dataset version, source URL, terms, checksum, retrieval date,
and allowed use in `docs/dataset-registry.md` before downloading or committing
anything. Source-dataset terms take precedence over a benchmark repository's
code license.

| Dataset/source | Capability represented | Proposed use | Fit to final personal-intuition claim | License/action |
|---|---|---|---|---|
| Existing `datasets/smoke` | Schema and deterministic edge retrieval | Unit and smoke tests only | None | Repository-owned synthetic data |
| [LongMemEval](https://github.com/xiaowu0162/LongMemEval) | Information extraction, multi-session reasoning, updates, temporal reasoning, and abstention | Memory-index and retrieval regression benchmark | Indirect | Repository reports MIT; register exact data artifact |
| [LoCoMo](https://github.com/snap-research/locomo) | Long conversational memory with timestamped evidence | Benchmark adapter for long-horizon retrieval | Indirect | Verify dataset terms before acquisition or redistribution |
| [LaMP](https://github.com/LaMP-Benchmark/LaMP) | Personalized language tasks using user profiles/history | Test retrieval-conditioned personalization methods | Indirect | Benchmark methods are CC BY-NC-SA; each underlying source retains its own terms; do not assume LaMP-6/Avocado is accessible |
| [PersonalLLM](https://huggingface.co/datasets/namkoong-lab/PersonalLLM) | Sparse preference learning across modeled personalities | Test cold-start and user-adaptation algorithms | Indirect | CC BY-NC 4.0; noncommercial research only |
| [PersonaLens](https://github.com/amazon-science/PersonaLens) | Personalized conversational-assistant evaluation | Optional later evaluation of profile inference | Indirect | CC BY-NC 4.0 |
| [Small World of Words](https://smallworldofwords.org/en/project/research) | Population-level free association norms | Remote-association probes or candidate prior experiments | Low; word-level and not personal | CC BY-NC-ND 3.0; evaluation/research only unless permission permits more |
| [ConceptNet](https://conceptnet.io/) | Typed commonsense relationships | Relation-type sanity checks or initialization | Low | CC BY-SA 4.0; preserve attribution/share-alike obligations |
| [ATOMIC 2020](https://github.com/allenai/comet-atomic-2020) | If-then social and causal commonsense relations | Generic causal/relation classifier experiments | Low | CC BY 4.0 |
| [OpenAlex](https://developers.openalex.org/) | Large directed scholarly citation graph with timestamps and metadata | Sampled scale tests for temporal link prediction | Low | CC0 data; record snapshot/API version |
| [WikiLinkGraphs](https://arxiv.org/abs/1902.04298) | Longitudinal Wikipedia hyperlink graphs | Optional scale and temporal-link stress test | Low | Verify distribution and source-content obligations before use |
| Remote Associates Test resources | Controlled remote association | Evaluation probe, never evidence of personalization | Low | Terms vary by item set; register each source independently |
| User-owned notes, chats, bookmarks, and explicit links | The user's historical concepts and choices | Weak supervision and candidate corpus after explicit consent | High but noisy | Private, local by default; never commit raw content |
| New user judgments under the repository schema | Directed graded personal relationships | Gold train/dev/test data | Direct | Private, local, revocable, and exportable |

There is no reason to acquire every public dataset. Start with the smallest
portfolio that tests orthogonal capabilities:

1. LongMemEval for temporal memory;
2. either LaMP or PersonalLLM for sparse personalization;
3. ConceptNet or ATOMIC for generic directed relation handling;
4. a small OpenAlex or WikiLinkGraphs sample only when scale testing becomes
   necessary;
5. SWOW or a properly licensed remote-association set only as a probe.

Acquisition does not automatically authorize pooling a dataset into training.
Use each source as a benchmark first. Any later pretraining experiment must
compare no public pretraining against one added source at a time and report
negative transfer on the private chronological set. Generic association data
may otherwise overwhelm the sparse personal signal the project is intended to
learn.

Do **not** scrape public Obsidian or Zettelkasten vaults by default. They usually
lack explicit negatives, represent a selected author population, and carry
privacy and licensing risk. They are also poor evidence of another person's
latent associations.

### 4.2 Five data tiers

#### Tier 0 — Deterministic smoke data

Purpose: validate schemas, chronology, metrics, CLI behavior, and leakage
guards. It must remain tiny and readable. Passing it proves only software
correctness.

#### Tier 1 — Public capability benchmarks

Purpose: test one capability at a time. Keep native task evaluation alongside
any IntuitionMap adapter so conversion does not erase the benchmark's meaning.
Do not merge public benchmark scores into the private headline metric.

#### Tier 2 — Controlled synthetic IntuitionMap data

Build a seeded generator only if it is needed to exercise relation types,
temporal leaks, contradiction cases, duplicates, hubs, and known failure modes.
Keep generation templates and seeds out of the prompt/context of models being
evaluated. Synthetic examples may train plumbing or test controlled behavior;
they cannot demonstrate personal fidelity.

#### Tier 3 — Weakly labeled user-owned history

With explicit consent, import immutable copies or hashes of user-owned notes,
chats, bookmarks, citations, and revision metadata. Candidate weak-positive
signals include:

- explicit hyperlinks, citations, and manually created backlinks;
- an explicit shared project or user-created tag;
- repeated co-reference followed by navigation or reuse;
- deliberate grouping, copying, or synthesis by the user.

Assign every weak label a source, confidence, and timestamp. Do not treat
temporal proximity, co-occurrence, a click, or a missing link as a negative.
Self-supervised link masking—hide a pre-existing explicit link and retrieve its
target—is useful for training and validation, but it measures reconstruction of
past behavior rather than discovery of unstated intuition.

#### Tier 4 — Small personal gold set

This is the irreducible evidence source. Make it inexpensive and resistant to
bias:

- Ask for `essential`, `valid`, `invalid`, or `uncertain` with one action.
- Keep relation typing and rationale optional during the first pass.
- Before showing model proposals, allow the user to name any essential prior
  thought they independently remember. Preserve this as the **discovery
  stream**.
- Separately record acceptance/rejection of model-selected candidates as the
  **proposal stream**. Never pool the streams without an exposure feature.
- For each new thought, use an initial review queue of about five candidates:
  two top-scored, one model-disagreement or high-uncertainty item, one
  diversity/remote item, and one randomly sampled item from a controlled
  temporal band.
- Blindly repeat 5–10% of judgments after a delay to estimate intra-rater
  stability and an empirical ceiling.
- Include hard invalids that are topically similar but not meaningfully linked.
- Keep an untouched chronological test window. Evaluation feedback from that
  window must never return to training.

An initial planning range is 150–300 real thoughts and roughly 750–1,500 quick
judgments, with 100–200 evaluable query thoughts. These are not success
guarantees. Continue or stop based on label-time measurements and learning
curves: if performance has plateaued well below useful levels, generating more
of the same labels is not justified.

#### Tier 5 — Future consented multi-user data

Only begin after a single-user personalized system beats the generic baseline.
Separate users at train/test time for generalization claims, retain a
within-user chronological test for adaptation claims, obtain explicit consent,
and provide deletion/export controls. Publish only a de-identified benchmark
whose re-identification and content-leakage risks have been reviewed.

### 4.3 Reduce the user's labeling burden

Use these methods in order:

1. Import explicit user-created links and organizational actions as weighted
   weak labels.
2. Train generic representations on compatible public data without pretending
   that it is personal data.
3. Use pairwise ranking or a small personal head over frozen embeddings before
   fine-tuning a large model.
4. Query labels where models disagree, confidence is poorly calibrated, or the
   example fills a relation/temporal coverage gap.
5. Cap active review at a user-chosen interruption budget; default to a
   short batch rather than interrupting every capture.
6. Request rationales only for sampled `essential` cases, ambiguous decisions,
   and error analysis.
7. Stop labeling when the confidence interval and learning curve show that more
   judgments are unlikely to change the current decision.

Active-learning selections may enter the training pool but never the protected
test set. Because proposal exposure changes what gets labeled, sampling
probability and proposal source must be recorded for later bias analysis.

## 5. Proposed system decomposition

The architecture should remain modular so each claim can be tested.

```text
immutable thought capture
        |
        v
thought encoder + metadata features
        |
        v
multi-channel temporal candidate retrieval
  lexical | dense | recency | explicit links
        |
        v
directed pair reranker
  verdict distribution + relation types + abstention
        |
        v
small user-specific adapter/calibrator
        |
        v
attributed typed graph
        |
        v
flat or graph retrieval for a downstream task
```

- A bi-encoder makes broad retrieval affordable.
- A cross-encoder or pairwise LLM can jointly attend to the tokens of two
  thoughts and their direction after retrieval.
- A lightweight personal layer can learn which generic relationships matter to
  this user.
- The graph is an external memory and retrieval structure, not proof that the
  base model has acquired human-like intuition.
- A later online policy may choose which memories to write, link, retrieve, or
  forget, but it must be evaluated separately from the link scorer.

## 6. Baseline and model ladder

Move up this ladder one controlled change at a time. A more complex level is
accepted only if it beats the strongest cheaper level at comparable information
access.

| Level | Model | Purpose |
|---|---|---|
| B0 | Random, most-recent, popularity/hub, and explicit-link oracles where applicable | Detect broken metrics and quantify trivial signal |
| B1 | Existing lexical-temporal baseline plus TF-IDF/BM25 variants | Strong, transparent offline floor |
| B2 | One reproducible local embedding model and, if budget permits, one stronger fixed embedding service | Measure semantic retrieval independent of reranking |
| B3 | Hybrid candidate union with reciprocal-rank fusion or a learned linear combiner | Test complementarity of lexical, dense, and temporal signals |
| B4 | Directed cross-encoder or prompted pairwise reranker | Distinguish relationship from similarity |
| B5 | Frozen generic features plus user-specific logistic, pairwise, or low-rank head and calibrator | Test whether sparse personal feedback adds signal |
| B6 | Typed graph features, Personalized PageRank, path features, or prize-collecting subgraph retrieval | Test multi-hop and structural retrieval |
| B7 | Parameter-efficient fine-tuning, temporal GNN, or learned memory policy | Use only after data-volume and learning-curve evidence justifies it |

For every level, ablate text, recency, tags, explicit links, personal feedback,
and graph features. Match candidate pool, context, model calls, and cost when
comparing systems.

## 7. Evaluation contract

The current [evaluation harness](evaluation-harness.md) remains authoritative
for label semantics, temporal direction, provenance, and paid-run controls.
Extend it without weakening those constraints.

### 7.1 Split policy

- Use capture time, never a random edge split.
- Run rolling-origin evaluation for drift: train on the past, tune on the next
  block, test on a later untouched block.
- Fit embeddings, indexes, scalers, hard-negative selection, thresholds, and
  graph statistics using only information available at that point in time.
- Keep queries—not individual edges—together within a split.
- In future multi-user work, report both unseen-user and adapted-user results.
- Hash the dataset manifest and split definition into every run artifact.

### 7.2 Metrics

**Candidate retrieval**

- Essential recall at fixed `k` as the first primary metric.
- Relevant (`essential` + `valid`) macro recall, hit rate, MRR, and graded
  nDCG at `k`.
- Known-invalid suggestions per query and invalid rate among judged results.
- Candidate coverage by relation type, time distance, and discovery/proposal
  stream.
- P50/P95 latency, index size, tokens, and monetary cost.

**Verdict and relation prediction**

- Macro F1 and per-class precision/recall.
- Direction accuracy and multi-label relation F1.
- Brier score or log loss, calibration error, risk-coverage curve, and
  abstention rate.
- Confusion between topical similarity and a user-meaningful relationship.

**Personalization**

- Absolute and relative delta over the strongest generic model at equal budget.
- Cold-start learning curve versus number of personal judgments.
- Rolling performance and calibration under drift.
- Performance by explicit versus associative links and by temporal distance.

**Graph and downstream utility**

- Flat-store versus graph retrieval with equal candidate and model budgets.
- User-blinded pairwise preference, task completion, factual/provenance errors,
  and time saved.
- Graph saturation, duplicate inflation, degree distribution, generic hubs,
  path-length distribution, and unsupported-edge rate.

**Human and safety**

- Median labeling time, skipped-question rate, interruption burden, and
  intra-rater agreement.
- Provenance inversion, temporal leakage, private-content escape, deletion
  propagation, and ungrounded explanation rate.

Report macro/query-level values as the default so prolific thoughts do not
dominate. Segment results, but do not select a favorable segment after seeing
test outcomes.

### 7.3 Statistical policy

- Create an experiment card before implementation with the hypothesis,
  intervention, primary metric, practical minimum effect, split, budget, and
  go/no-go rule.
- Compare models on identical queries and use paired, query-level bootstrap
  confidence intervals. Add a paired permutation/randomization test when the
  sample size supports it.
- Report the effect size and interval, not only a p-value.
- Lock hyperparameters and thresholds before opening the protected test result.
- Use fixed recorded seeds and repeat stochastic systems enough to expose
  run-to-run variance.
- Correct broad exploratory sweeps for multiple comparisons or label them
  exploratory.
- Estimate intra-rater reliability; do not demand model performance beyond an
  unstable human ceiling without investigating the labels.
- LLM-based graders may support error triage, but headline personal and utility
  results require user judgments or objective task outcomes.

### 7.4 Provisional advancement rules

After the pilot estimates variance, replace the provisional practical effects
below with preregistered values. Never adjust them after viewing the protected
test result.

| Gate | Minimum evidence to advance |
|---|---|
| G0 — Correctness | Schema, chronology, leakage, determinism, and paid-run guard tests pass; smoke results are reproducible from a clean environment. |
| G1 — Data readiness | Every acquired dataset has a data card, exact license/terms, checksum, version, adapter tests, and a written statement of which claim it can and cannot support. |
| G2 — Retrieval | A candidate system improves essential recall@10 by a provisional 5 percentage points absolute or 10% relative over the strongest cheaper baseline; the paired 95% interval excludes zero; known-invalid exposure stays within a preregistered tolerance. |
| G3 — Label feasibility | Median judgment time and completion rate make the proposed label budget sustainable; repeated-label agreement is high enough for the intended verdict granularity. |
| G4 — Personalization | A personal model beats the strongest generic model on the untouched chronological test under the G2 statistical rule and demonstrates a useful cold-start curve. |
| G5 — Graph value | A graph-enabled system improves a preregistered downstream metric over flat retrieval at matched cost, without generic-hub or unsupported-edge regression. |
| G6 — Novel association | Blinded review shows a preregistered gain in accepted useful remote/contradictory links without a material invalid-suggestion increase. |
| G7 — Product/research claim | The effect replicates, provenance and deletion audits pass, limitations are documented, and the wording stays within the claim ladder. |

Provenance inversions and temporal leakage have a target of zero in adjudicated
audits. Any occurrence blocks the affected result until diagnosed and rerun.

## 8. Execution roadmap

The checkboxes record repository-level completion. An agent may work on a later
research item in parallel, but may not use it to bypass an earlier evidence
gate.

### Phase 0 — Freeze the research contract

- [x] Define immutable thoughts, directed verdicts, chronological evaluation,
  core metrics, failure codes, and spend controls.
- [x] Add a deterministic smoke dataset and lexical-temporal baseline.
- [x] Create `docs/literature-matrix.md` using Section 3.
- [x] Create `docs/dataset-registry.md` with dataset-card and license fields.
- [x] Create `docs/experiment-template.md`.
- [x] Create `docs/decision-log.md`; include rejected approaches and negative
  results.
- [x] Re-run all existing validation and tests from a clean environment and
  record the commands and results.

**Exit:** G0 passes and all scientific decisions have an auditable home.

### Phase 1 — Acquire only orthogonal public evidence

- [x] Register and build a minimal LongMemEval adapter.
- [x] Select **one** sparse-personalization benchmark: LaMP or PersonalLLM.
- [x] Select **one** generic relation source: ConceptNet or ATOMIC.
- [x] Preserve native benchmark evaluation and add only the minimum
  IntuitionMap-compatible view needed for shared components.
- [x] Add download/preparation scripts, content hashes, small licensed test
  fixtures, and adapter unit tests. Do not commit restricted raw data.
- [x] Record why LoCoMo, SWOW, OpenAlex, WikiLinkGraphs, or any other source is
  deferred before acquiring it.

**Exit:** G1 passes for every acquired artifact. The portfolio tests memory,
personalization, and relation handling without pretending to be personal gold.

### Phase 2 — Strengthen retrieval and measurement

- [x] Add random, most-recent, TF-IDF/BM25, and explicit-link controls.
- [x] Add an embedding interface and one reproducible local embedding baseline.
- [x] Add hybrid candidate fusion with deterministic tie handling.
- [x] Add graded nDCG, calibration-ready prediction records, paired bootstrap
  intervals, rolling chronological splits, and subgroup reports.
- [x] Add tests for same-query grouping, future-data leakage, duplicates, empty
  judgments, unknown labels, and invalid-exposure metrics.
- [x] Run one-variable ablations and write experiment cards before each run.
- [x] Perform error analysis using the existing failure taxonomy.

**Exit:** G2 passes on at least one appropriate evaluation source, or the
decision log explains why retrieval signal is inadequate.

### Phase 3 — Build the low-burden private-data path

- [x] Define explicit consent, local storage, redaction, export, and deletion
  behavior before importing any content.
- [x] Add an importer that preserves immutable source text, timestamps, source
  IDs, explicit links, and provenance without committing private content.
- [x] Add a weak-label table with source and confidence; never overwrite gold
  judgments.
- [x] Build an annotation queue/export-import workflow with one-action verdicts,
  optional relation/rationale, sampling source, exposure status, and response
  time.
- [x] Support discovery-stream links before showing proposals.
- [x] Add blind repeat judgments and controlled random/temporal samples.
- [ ] Pilot the workflow, measure burden and consistency, and revise verdict or
  relation granularity before scaling.
- [ ] Freeze a chronological gold test manifest. The sealed implementation is
  tested synthetically; freezing the real manifest requires consented input.

**Exit:** G3 passes. If labeling is too slow or inconsistent, simplify the task
before collecting more data.

### Phase 4 — Test whether personalization is real

- [ ] Freeze the strongest generic candidate and reranking baseline.
- [ ] Compare a calibrated generic model with a small personal linear/pairwise
  head on frozen features.
- [ ] Add explicit invalid hard negatives; mask `uncertain` and unknown pairs
  from ordinary negative training.
- [ ] Compare weak-only, gold-only, and weak-plus-gold training.
- [ ] Plot cold-start and time-ordered learning curves.
- [ ] Test time decay or drift adaptation only after a stationary model is
  established.
- [ ] Inspect errors by relation, temporal distance, proposal exposure, and
  explicit versus associative link.

**Exit:** G4 passes. If it fails, do not compensate with a larger opaque model
until label quality, task stability, and feature sufficiency have been tested.

### Phase 5 — Add typed graph memory

- [ ] Store model-proposed and user-confirmed edges separately with versioned
  confidence and provenance.
- [ ] Add graph-health reports and controls for hubs, duplicates, unsupported
  edges, and stale relationships.
- [ ] Compare direct retrieval, one-hop expansion, Personalized PageRank, and a
  constrained subgraph method at matched budgets.
- [ ] Add contradiction and provenance-aware relation types.
- [ ] Evaluate graph ablations on multi-hop retrieval and a downstream task.
- [ ] Do not allow model-generated summaries to mutate immutable source
  captures; store them as derived, versioned artifacts.

**Exit:** G5 passes. A graph that only improves visual organization does not
justify a claim about reasoning or intuition.

### Phase 6 — Evaluate remote association and real utility

- [ ] Define "novel but useful" before testing it: unexpectedness must be
  separated from relevance and correctness.
- [ ] Add properly licensed controlled association/analogy probes.
- [ ] Sample real distant, contradictory, and cross-project suggestions for
  blinded user review.
- [ ] Choose one real downstream task, such as resurfacing a forgotten idea,
  producing a cited synthesis, detecting a contradiction, or supporting a
  planning decision.
- [ ] Compare no memory, flat retrieval, generic graph, and personalized graph
  at matched information and model budgets.
- [ ] Measure utility, provenance errors, latency, cost, and trust—not only
  subjective surprise.

**Exit:** G6 passes and downstream evidence supports claim 4.

### Phase 7 — Replication and responsible release

- [ ] Write a protocol and consent process before recruiting anyone.
- [ ] Power the study using pilot effect sizes rather than a convenient sample.
- [ ] Separate within-user adaptation from unseen-user generalization.
- [ ] Test deletion, export, redaction, and memorization leakage.
- [ ] Replicate the preregistered primary analysis.
- [ ] Release code, schemas, synthetic fixtures, and reproducible public-data
  adapters first. Release human data only when consent and privacy review
  explicitly permit it.

**Exit:** G7 passes before making a broad claim about modeling human intuition.

## 9. Experiment-card minimum

Every nontrivial run should answer these questions before code or paid inference:

```yaml
id:
date:
research_question:
hypothesis:
decision_this_can_change:
dataset_versions_and_hashes:
train_dev_test_time_boundaries:
intervention:
strongest_comparable_baseline:
information_available_to_each_system:
primary_metric:
secondary_metrics:
practical_minimum_effect:
statistical_test_and_interval:
invalid_exposure_tolerance:
latency_token_and_cost_budget:
privacy_risks:
expected_failure_modes:
stop_go_rule:
```

After the run, append the environment, model identifiers, prompts/config hashes,
raw artifact path, result, interval, failure analysis, and decision. Negative
results remain in the decision log.

## 10. Repository conventions for this program

The implementation agent should converge toward the following separation:

```text
configs/                 versioned experiment configurations
datasets/
  smoke/                 committed deterministic fixtures
  private/               ignored user-owned content and labels
  external/              ignored downloaded public artifacts
docs/
  dataset-registry.md    sources, versions, terms, hashes, allowed uses
  decision-log.md        accepted and rejected research decisions
  experiment-template.md preregistration and result template
  literature-matrix.md   evidence extraction
runs/                    ignored immutable run outputs
src/
  intuition_map_eval/    evaluation contract and metrics
  intuition_map_data/    adapters, validation, manifests, provenance
  intuition_map_models/  retrieval, reranking, personalization, graph methods
tests/                   leakage, metric, adapter, and reproducibility tests
```

- Raw private data and restricted public datasets must remain ignored.
- Prefer acquisition scripts and manifests over vendored copies.
- Every derived artifact points back to immutable sources and code/config
  versions.
- Cache outputs by dataset, model, prompt/config, and code hashes.
- Paid inference remains opt-in and budget-capped as specified by the current
  harness.
- Do not change a metric or split in place; version it and preserve comparability.

## 11. Principal risks and controls

| Risk | Why it can invalidate the work | Control |
|---|---|---|
| Public-data mismatch | Generic memory scores may be mistaken for personal intuition | Map each dataset to a specific capability and claim; require personal gold for personal claims |
| Benchmark contamination | A foundation model may have seen public test content during pretraining | Treat public scores as component checks, record contamination risk, and reserve private post-training chronological data for the central claim |
| Exposure/selection bias | The model controls which pairs the user gets to label | Preserve discovery and proposal streams, sampling source, random exploration, and exposure probability |
| False negatives | Unlabeled pairs may still be meaningful | Only explicit `invalid` is negative; use positive-unlabeled methods when appropriate |
| Weak-label contamination | Links, tags, and clicks encode convenience as well as meaning | Retain signal provenance, confidence, and weak/gold ablations |
| Temporal leakage | Future links, summaries, or graph statistics make results impossible in deployment | Timestamp every artifact and test point-in-time reconstruction |
| Graph saturation | Generic hubs make everything appear connected | Degree/hub reports, diversity constraints, edge thresholds, and matched flat baselines |
| Confirmation/echo-chamber effects | Personalization may reinforce prior beliefs | Retrieve contradictions and counterevidence; measure diversity and disagreement separately |
| LLM self-evaluation | A related model may reward its own style or explanation | Human or objective headline outcomes; LLM graders only for triage |
| Label drift | The user's projects and interpretation change | Rolling evaluation, dated judgments, repeats, recalibration, and optional superseding labels |
| Privacy and memorization | Personal thoughts may leak through services or artifacts | Local-first storage, explicit service consent, redaction, access logs, deletion tests, and no raw commits |
| Model/version drift | Hosted APIs can change invisibly | Record model snapshots, prompts, responses, dates, cost, and repeat a stable local control |
| Complexity bias | A sophisticated graph/model may look more convincing without working better | Baseline ladder, one-variable experiments, equal budgets, and stop/go gates |

## 12. Instructions for the next agent

1. Read `README.md`, `docs/evaluation-harness.md`, and this document completely.
2. Inspect the worktree and preserve unrelated user changes.
3. Start at the first unchecked item whose prerequisites are complete.
4. For research, create the literature matrix and dataset registry before
   downloading data or proposing a final architecture.
5. For implementation, write an experiment card before changing the model,
   metric, split, or paid-inference configuration.
6. Implement the smallest change that can test the stated hypothesis, add
   proportionate tests, and run deterministic/offline checks first.
7. Never use synthetic or public benchmark success as evidence that the system
   learned the user's intuition.
8. Never treat an unlabeled pair as invalid, and never train on protected test
   feedback.
9. Record complete results, including null and negative results, then update the
   checkbox and decision log only when its evidence gate actually passes.
10. Stop and document the blocker if completion would require private data,
    paid inference, incompatible terms, or a change in scientific scope not
    already authorized.

## Definition of program success

The program succeeds when a reproducible personalized system, using only
information available at capture time:

- retrieves more user-marked essential relationships than the strongest generic
  alternative within a small review budget;
- maintains calibrated abstention and acceptable invalid exposure;
- demonstrates that the graph improves at least one real task over matched flat
  retrieval;
- remains attributable, private, reversible, and affordable;
- and reproduces beyond the original user before any general claim about human
  intuition is made.

If personal feedback does not improve held-out judgments or downstream utility,
that is a valuable falsification. The system should then remain a generic
memory/retrieval tool rather than have its behavior relabeled as intuition.
