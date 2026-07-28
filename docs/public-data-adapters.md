# Phase 1 public-data adapters

## Scope

Phase 1 registers three orthogonal public capability checks:

| Registry ID | Native capability | IntuitionMap adapter view | Explicit non-claim |
|---|---|---|---|
| `LME-001` | Long-term conversational memory QA and evidence retrieval | Questions, native types, timestamp strings, sessions, turns, answers, and evidence-session IDs | Not personal thought-link fidelity |
| `PLLM-001` | Sparse preference adaptation over fixed candidate responses | Prompt/native IDs, eight response/model pairs, and ten reward-profile score vectors | Reward-model profiles are not this user's preferences or intuition |
| `ATOMIC-001` | Directed commonsense graph completion | Native head/relation/tail triples and train/dev/test membership | Population commonsense is not a personal association map |

The adapters are read-only and native-preserving. They do not convert public
labels into `essential`, `valid`, `invalid`, or `uncertain` judgments, and their
scores must never be pooled into a personal headline metric.

## Reproducible acquisition

The exact revisions, URLs, byte lengths, SHA-256 values, license evidence, and
claim boundaries live in `configs/data/`.

```powershell
$env:PYTHONPATH = "src"
python -m intuition_map_data.acquisition `
  --manifest configs/data/longmemeval-oracle.json
python -m intuition_map_data.acquisition `
  --manifest configs/data/personalllm-test.json
python -m intuition_map_data.acquisition `
  --manifest configs/data/atomic2020.json
```

Artifacts are written only under ignored `datasets/external/`. A download is
written to a partial file and promoted only after its registered byte length
and SHA-256 both match. Existing files are reused only after the same checks.
Traversal outside the configured root is rejected.

The ATOMIC data uses a byte-pinned mirror because the historical AI2 S3 URL
returned HTTP 404 during the 2026-07-28 review. The official repository revision
and README remain the source and license evidence; the mirror supplies the
registered release bytes.

## Native validation

Install the pinned optional Parquet reader in an ignored environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[public-data]"
.\.venv\Scripts\python.exe -m intuition_map_data.validate_public
```

Validation on 2026-07-28 used Python 3.12.4 and PyArrow 25.0.0:

| Dataset | Validated native contents |
|---|---|
| LongMemEval | 500 questions, 948 sessions, 10,960 turns, 948 evidence sessions, six native question types |
| PersonalLLM | 1,000 test records, eight candidates per prompt, ten complete reward profiles |
| ATOMIC 2020 | 1,076,880 train, 102,024 dev, and 152,209 test triples across 23 relations; bundled CC BY 4.0 heading present |

The reusable command first re-verifies every artifact against its registry
manifest, then parses every selected native record. It makes no network or
model request in verification mode.

## Native conditions retained

Two fixture-incomplete assumptions were falsified during full-data validation:

1. LongMemEval contains 32 integer answers for counting questions. The adapter
   retains `str | int` rather than coercing answers to text.
2. ATOMIC 2020 contains 16 training triples with an empty tail; dev and test
   contain none. The adapter retains those records with `is_complete=False`.
   Any later training filter must state and count this exclusion explicitly.

The first ATOMIC acquisition attempt also used a rounded webpage byte count.
The acquisition gate rejected the file and deleted the partial copy before
promotion. The manifest was corrected to the immutable mirror metadata value
of 12,580,048 bytes; its SHA-256 was unchanged.

## Native evaluation remains authoritative

- LongMemEval answer/evidence evaluation remains the benchmark's QA/retrieval
  task. The adapter does not replace its answer scorer.
- PersonalLLM remains a fixed-candidate preference/reward task. The adapter
  exposes profiles and candidates without translating them to thought links.
- ATOMIC remains directed triple completion over its native splits and
  relations. The adapter does not infer personal relevance.

The adapters exist so retrieval, representation, and personalization
components can share audited loading code while the original benchmark
meaning remains visible.

## Terms and release controls

- Raw external artifacts remain ignored and are not included in Git.
- Committed adapter fixtures are original synthetic schema examples released
  under CC0 1.0; they copy no benchmark records.
- PersonalLLM's pinned card declares CC BY 4.0 but lists upstream prompt sources
  without a complete terms inventory. Its raw artifact is therefore restricted
  here to local benchmark evaluation; redistribution and product training stay
  blocked pending a separate upstream review.
- Public benchmark success supports at most claim C2. It cannot establish
  personal associative fidelity, downstream utility, or cross-user
  generalization.
