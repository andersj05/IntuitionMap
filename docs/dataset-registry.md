# IntuitionMap dataset registry

**Registry version:** 0.1
**Last source/terms review:** 2026-07-28
**Acquisition state:** three Phase 1 artifacts are verified in ignored local
storage; no raw external or private dataset is committed.

This registry is an engineering control, not legal advice. Source-dataset terms
take precedence over a benchmark repository's code license. A row marked
`candidate` is not approval to download, train on, redistribute, or use in a
product.

## Status and claim vocabulary

- `committed-synthetic`: repository-authored fixture, safe to version.
- `candidate-terms-review`: potentially useful, but exact artifact and terms
  must be pinned before acquisition.
- `candidate-choice`: one option in a mutually exclusive Phase 1 choice.
- `registered-pending-acquisition`: exact artifact, terms evidence, and checksum
  are pinned, but the ignored local copy has not yet been verified.
- `registered-local`: exact ignored local artifact has passed size and SHA-256
  verification; this status does not permit redistribution.
- `deferred`: no current experiment justifies acquisition.
- `blocked`: unresolved terms, privacy, or scientific-fit issue.
- `private-future`: may be created locally only after the Phase 3 controls and
  explicit user consent exist.

Claim support uses the ladder from the
[research plan](research-and-implementation-plan.md):

- C1 software correctness
- C2 generic retrieval/capability
- C3 personal associative fidelity
- C4 downstream utility
- C5 cross-user generalization

## Registry

| ID | Source and proposed pinned version | Status | Capability / proposed use | Claims it can support | Claims it cannot support | License or terms evidence | Allowed use at this stage | Redistribution / commit rule | Artifact retrieval and SHA-256 | Required next action |
|---|---|---|---|---|---|---|---|---|---|---|
| IM-SMOKE-001 | Repository `datasets/smoke`, manifest schema `0.1.0` | `committed-synthetic` | Schema, chronology, leakage, deterministic ranking, and metric smoke tests. | C1 only. | C2–C5 and any product-quality claim. | Project-authored synthetic data; manifest declares no personal data. | Offline tests and examples. | May remain committed with the repository. | Retrieved: repository creation; hashes are in the data card below. | Recompute hashes whenever any fixture file changes. |
| LME-001 | [Official cleaned HF release](https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned) revision `98d7416c24c778c2fee6e6f3006e7a073259d48f`; oracle artifact only | `registered-local` | Temporal memory, multi-session reasoning, updates, evidence retrieval, abstention; preserve native QA. | C2 temporal-memory capability. | C3–C5; histories/questions are not the user’s latent thought links. | Pinned dataset card declares MIT; card SHA-256 `fe31783d4e5d132681a25e4192e85def8edd214094939879f5283818c0a4a3e0`. | Local component evaluation under the pinned terms. | Raw external data stays ignored and is not redistributed from this repository. | `longmemeval_oracle.json`, 15,388,478 bytes, SHA-256 `821a2034d219ab45846873dd14c14f12cfe7776e73527a483f9dac095d38620c`; verified locally 2026-07-28; retrieval specified in `configs/data/longmemeval-oracle.json`. | Reverify before each run and preserve native QA/evidence evaluation alongside any shared retrieval view. |
| LME-S-001 | Same official cleaned release/revision as LME-001; `longmemeval_s_cleaned.json` with distractor sessions | `registered-local` | Discriminating evidence-session retrieval for Phase 2 baseline comparisons. | C2 generic temporal-memory retrieval capability. | C3–C5 and invalid-link control; answer-session labels provide positives but not explicit invalids. | Same pinned MIT dataset card as LME-001. | Local retrieval evaluation under `EXP-P2-001` and `EXP-P2-002`. | Raw 277 MB artifact stays ignored and is not redistributed. | 277,383,467 bytes; SHA-256 `d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442`; verified locally 2026-07-28; retrieval specified in `configs/data/longmemeval-s.json`. | Preserve native history-envelope availability. The audit found 1,475 sessions after and 3 at `question_date`, including 75 after-date evidence sessions; do not silently filter or repair them. Exclude 30 `_abs` queries from retrieval scoring per the official protocol. |
| LOCOMO-001 | [LoCoMo official repository](https://github.com/snap-research/locomo), exact commit/archive not pinned | `deferred` | Long conversational history with timestamped sessions and QA/event summaries. | C2 memory capability. | C3–C5; ten generated conversations are not personal associative gold. | Official `LICENSE.txt` is CC BY-NC 4.0. Dataset records can include third-party image URLs, which may carry separate rights. | Noncommercial research planning only. | Do not fetch linked images; do not commit raw data. Any later sharing must satisfy attribution/NC and third-party terms. | Artifact not retrieved; SHA-256 `—`. Source checked 2026-07-28. | Keep deferred while LongMemEval covers the temporal-memory role; register an exact archive and third-party-content policy before reconsidering. |
| LAMP-001 | [LaMP official repository](https://github.com/LaMP-Benchmark/LaMP), task and revision not selected | `deferred` | Sparse personalization from user history; retain native classification/generation evaluation. | C2 personalization capability. | C3–C5; behavior/style proxies are not directed personal thought links. | LaMP code/data-creation methods are CC BY-NC-SA 4.0; official README states each underlying dataset retains its own terms. Avocado/LaMP-6 is not publicly available. | Literature and method comparison only. | Never treat the umbrella license as covering source data. No raw external data in Git. | Artifact not retrieved; SHA-256 `—`. Source checked 2026-07-28. | Deferred because PersonalLLM covers sparse adaptation with one pinned artifact and a clearer top-level card; reconsider only if LaMP exposes a capability PersonalLLM cannot test. |
| PLLM-001 | [PersonalLLM official HF dataset](https://huggingface.co/datasets/namkoong-lab/PersonalLLM) revision `643192faf99effc9403ce80dc5a38a016b6f7247`; test split only | `registered-local` | Cold-start preference adaptation across simulated reward-model personalities. | C2 personalization capability. | C3–C5; preferences are reward-model-generated and do not represent this user’s intuition. | Pinned official card declares CC BY 4.0; card SHA-256 `89609a728dd1b32501a334f81c071a21d34c4d237dc1c7adf56f149ebd6d1cd0`. This resolves the earlier unpinned CC BY-NC planning note for this exact revision, while upstream prompt-source terms remain underspecified. | Local benchmark evaluation only; no product training or redistribution without separate upstream-source review. | Raw Parquet stays ignored and is not redistributed from this repository. | `test-00000-of-00001.parquet`, 8,896,944 bytes, SHA-256 `92b6daccd6232874af757569814ab63fb3bc3448e1dbbe00791ce2e98a608ab2`; verified locally 2026-07-28; retrieval specified in `configs/data/personalllm-test.json`. | Reverify before each run; keep the native preference task separate and preserve the upstream-source restriction. |
| PLENS-001 | [PersonaLens official repository](https://github.com/amazon-science/PersonaLens), revision not pinned | `deferred` | Personalized conversational-assistant evaluation and profile inference. | C2 personalization capability. | C3–C5; synthetic/profile benchmark, not personal thought-link fidelity. | Official repository states CC BY-NC 4.0; reproduction also requires Amazon Bedrock/model access with separate service terms and cost. | Literature review only. | Do not acquire or run paid generation during current phases. No raw data in Git. | Artifact not retrieved; SHA-256 `—`. Source checked 2026-07-28. | Reconsider only if the selected Phase 1 personalization benchmark leaves a specific uncovered capability. |
| SWOW-001 | [Small World of Words official research release](https://smallworldofwords.org/en/project/research), language/release not selected | `deferred` | Population word-association norms for controlled remote-association probes. | C2 probe only. | C3–C5; population word norms are neither thought-level nor personal. | Official project terms: personal/research use only, no redistribution or commercial use without permission; CC BY-NC-ND 3.0 is stated for the project/release. | Source inspection and probe design only. | Never commit, repackage, or publish modified data without permission. | Artifact not retrieved; SHA-256 `—`. Source checked 2026-07-28. | Define a preregistered probe and exact language/release before requesting permission or downloading. |
| CN5-001 | [ConceptNet 5](https://conceptnet.io/), exact 5.x release not selected | `deferred` | Typed generic commonsense relations and graph/relation sanity checks. | C2 generic relation handling. | C3–C5; aggregated commonsense cannot establish a user’s associations. | Official site states CC BY-SA 4.0. Individual source attribution and ShareAlike obligations must be preserved. | Literature and method comparison only. | No raw dump in Git. Any distributed adapted database must satisfy attribution/ShareAlike obligations. | Artifact not retrieved; SHA-256 `—`. Source checked 2026-07-28. | Deferred because ATOMIC 2020 is directed, materially smaller, and has simpler source/attribution scope for the Phase 1 relation check. |
| ATOMIC-001 | [ATOMIC 2020 official repository](https://github.com/allenai/comet-atomic-2020) revision `33129ff9fbab126a98ce03f10017c405a553aeab`; February 2021 release archive | `registered-local` | Directed if-then social, causal, and intent relation handling. | C2 generic directed-relation capability. | C3–C5; generic crowd knowledge is not personal intuition. | Pinned official README says data are CC BY and code is Apache 2.0; README SHA-256 `dd4299fe8c78cf5322e370006d0c72c1e7ef6068149096309b81f24b38e0d6f4`. The release bundles CC BY 4.0 text. | Local relation-component evaluation with attribution and content-warning controls. | Raw archive/extraction stays ignored. A tiny attributed fixture may be committed under CC BY 4.0. | `atomic2020_data-feb2021.zip`, 12,580,048 bytes, SHA-256 `47c5f362ab4a3ea58c4962eebfdfd1c5420d3780e74cd3fe09efeef64f941c2b`; verified locally 2026-07-28; byte-pinned mirror and provenance are specified in `configs/data/atomic2020.json`. | Reverify before each run; retain the 16 incomplete train tails explicitly and preserve native splits. |
| OA-001 | [OpenAlex](https://developers.openalex.org/download/overview), exact data version/snapshot or API query not selected | `deferred` | Large directed citation graph with timestamps for future scale and temporal-link stress tests. | C2 scale/temporal plumbing only. | C3–C5; citation behavior is not personal thought association. | Official OpenAlex documentation states data are CC0. Current documentation distinguishes public snapshots, paid update frequencies, and data versions; exact release notes must be pinned. | Design a small deterministic query/sample only when scale is the active question. | Do not download the full snapshot by default. Store query, response/version metadata, and a content hash; raw external sample remains ignored unless explicitly approved. | Artifact not retrieved; SHA-256 `—`. Source checked 2026-07-28. | Defer until a measured scale bottleneck exists; prefer a bounded API/CLI sample with recorded data version. |
| WLG-001 | [WikiLinkGraphs paper](https://arxiv.org/abs/1902.04298) and [dataset page](https://consonni.dev/datasets/wikilinkgraphs/), archive not selected | `deferred` / `blocked` pending archive terms | Longitudinal multilingual hyperlink graph for temporal-link scale tests. | C2 scale/temporal plumbing only. | C3–C5; hyperlinks reflect editorial behavior, not a user’s latent thought links. | Paper/dataset licensing must be reconciled with Wikimedia source-content terms (CC BY-SA/GFDL as applicable). Do not infer artifact rights from code or paper access. | Metadata inspection only. | No archive download or redistribution until exact archive license, attribution, and source-content obligations are recorded. | Artifact not retrieved; SHA-256 `—`. Source checked 2026-07-28. | Keep deferred behind OpenAlex; resolve terms only if it becomes the chosen temporal graph source. |
| RAT-001 | Remote Associates Test resources; no item set selected | `blocked` | Controlled convergent remote-association probe. | At most C2 probe evidence. | C3–C5 and general creativity/intuition claims. | Rights vary by paper, item set, and adaptation; no blanket license was located in this review. | Define desired construct and inspect candidate item sources. | Do not scrape, copy, or publish test items without explicit compatible terms. | Artifact not retrieved; SHA-256 `—`. Source checked 2026-07-28. | Register each candidate set independently or create a project-authored controlled probe that does not copy protected items. |
| USER-HISTORY-001 | User-owned notes, chats, bookmarks, citations, links, and revision metadata | `private-future` | Weak positive signals and candidate history after explicit consent. | Indirect evidence toward C3 when provenance is retained. | Alone cannot support C3–C5; organizational behavior is noisy and missing links are unknown. | User ownership/authorization and each source service’s export terms control use. Consent must be explicit, scoped, revocable, and recorded. | None until Phase 3 consent, local storage, redaction, export, and deletion behavior is implemented and tested. | Raw content stays in ignored `datasets/private/`, is encrypted/access-controlled as designed, and is never committed or sent to a model service without separate consent. | Not imported; SHA-256 `—`. | Ask the user only after Phase 3 safeguards exist; present exact fields, purposes, service boundaries, retention, and deletion behavior before import. |
| USER-GOLD-001 | New directed verdicts created under the IntuitionMap schema | `private-future` | Gold `essential`/`valid`/`invalid`/`uncertain` judgments, discovery/proposal stream, optional relation/rationale, repeats. | Direct C3 evidence; later contributes to C4. | One user cannot support C5. | User-created private data under explicit consent; revocable and exportable. | None until annotation UI, exposure logging, blind repeats, and protected chronological split controls pass Phase 3 tests. | Never commit raw judgments; derived aggregate results must pass privacy review. Protected test feedback never returns to training. | Not collected; SHA-256 `—`. | When ready, ask for a small pilot, explain the label budget, and stop if burden/reliability fails G3. |

## Data card for the committed smoke fixture

```yaml
id: IM-SMOKE-001
name: synthetic-linking-smoke
registry_version: 0.1
schema_version: 0.1.0
owner: IntuitionMap repository
provenance: project-authored synthetic data
contains_personal_data: false
purpose:
  - schema validation
  - temporal-direction and leakage checks
  - deterministic ranking and metric smoke tests
annotation:
  candidate_pool: all_prior_thoughts
  exhaustive: false
  unlabeled_pairs_are: unknown
split: no learned-model split; deterministic smoke evaluation only
allowed_claims:
  - C1 software correctness
disallowed_claims:
  - generic retrieval quality
  - personal associative fidelity
  - downstream utility
  - cross-user generalization
license: repository-authored fixture distributed with project
files:
  manifest.json:
    canonical_text_sha256: a44eea68fc49b925bb4d4121be13aabd00e996ea9ea447d94b0cce71f37055d9
  thoughts.jsonl:
    canonical_text_sha256: 55724db113579469df36bd4a9ad83ed17bdddf0386e2a7e25247bd2524de53b8
  judgments.jsonl:
    canonical_text_sha256: e052d661da1a4feb5fd153bb4af8fa1316ebc79c18cbf90dd06e23dedc5ec727
hash_method: UTF-8 text with physical CRLF/CR newlines normalized to LF
last_hash_verification: 2026-07-28
```

## Required card fields before any future acquisition

Copy this block into the registry or a linked data card before a download:

```yaml
id:
name:
status:
source_owner:
source_url:
artifact_url:
upstream_revision_or_release:
retrieved_at_utc:
retrieval_command_or_script:
files_and_sha256:
license_name:
license_url:
license_file_sha256:
license_scope:
upstream_sources_and_terms:
allowed_uses:
prohibited_uses:
redistribution_rule:
commercial_use_rule:
attribution_requirements:
contains_personal_or_sensitive_data:
privacy_review:
capability_tested:
claims_supported:
claims_not_supported:
native_task_and_metrics:
intuition_map_adapter_scope:
split_policy:
contamination_risk:
known_limitations:
adapter_tests:
owner:
reviewed_by:
reviewed_at:
```

## Acquisition gate

An external dataset can move from `candidate` to `registered` only when all of
the following are true:

1. A specific experiment card names the capability and decision the data can
   change.
2. The exact artifact revision, source URL, retrieval date, and SHA-256 are
   recorded.
3. Code, benchmark, and every upstream data license are distinguished.
4. Allowed use, redistribution, attribution, commercial restrictions, and
   personal-data risk are explicit.
5. The artifact is downloaded by a reproducible script into ignored
   `datasets/external/`.
6. Native evaluation is preserved; any IntuitionMap adapter has fixture tests.
7. The registry states which claim the dataset cannot support.

The preregistered Phase 1 portfolio is LongMemEval oracle, PersonalLLM test, and
ATOMIC 2020. The selection is capability-scoped, not an assertion that these
sources represent personal intuition. Exact acquisition inputs live in
`configs/data/`, and `configs/experiments/EXP-P1-001-data-readiness.yaml`
defines the deterministic G1 decision.
