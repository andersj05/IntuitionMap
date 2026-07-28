# IntuitionMap validation record

## VAL-0001 — Phase 0 correctness gate

**Date:** 2026-07-28
**Status:** pass after one diagnosed portability fix
**Claim supported:** C1 software correctness only
**Cost:** $0; no API requests
**Environment:** Windows, PowerShell, Python 3.14.2

### Isolation method

A new unique directory under the operating-system temporary directory was
created. Only these current source inputs were copied into it:

```text
pyproject.toml
README.md
src/
tests/
datasets/smoke/
configs/
```

The copy excluded `.git`, secrets/environment files, prior run artifacts,
private/external data, Python caches, the untracked `web/` scaffold, and
`node_modules`. No dependency installation, network request, model call, or
server process was used.

### Commands

From the fresh copy:

```powershell
$env:PYTHONPATH = "src"
python --version
python -m compileall -q src tests
python -m unittest discover -s tests -v
python -m intuition_map_eval validate --dataset datasets/smoke
python -m intuition_map_eval run `
  --dataset datasets/smoke `
  --config configs/lexical-baseline.json `
  --output run-a
python -m intuition_map_eval run `
  --dataset datasets/smoke `
  --config configs/lexical-baseline.json `
  --output run-b
```

The deterministic comparison checked:

- exact SHA-256 equality for `predictions.jsonl`;
- exact equality for `config.resolved.json` and `usage.json`;
- metric equality after excluding only measured `runtime.wall_seconds`;
- equality of the dataset fingerprint stored in both manifests.

Run IDs, creation timestamps, and wall time are expected to differ and were not
treated as algorithm output.

### Results

| Check | Result |
|---|---|
| Python | 3.14.2 |
| Byte compilation | pass |
| Unit tests | 10 passed in 0.346 seconds |
| Schema/count validation | 10 thoughts; 15 judgments; 6 essential, 5 valid, 4 invalid |
| Temporal leakage rejection | pass |
| Unknown-versus-invalid metric behavior | pass |
| Duplicate prediction rejection | pass |
| Paid-gate and budget-ledger tests | pass |
| Two-run prediction equality | pass |
| Two-run metric equality excluding wall time | pass |
| Two-run resolved-config equality | pass |
| Two-run usage-ledger equality | pass |
| Two-run dataset-fingerprint equality | pass |
| Paid API requests | 0 |
| Estimated cost | $0 |

Stable identifiers:

```text
dataset_fingerprint =
  7eb86af0562b26b546b99810817f4f44eda52615fc0992a8369fcfcba30d4418
config_canonical_text_sha256 =
  8edc89b3bb4b91f489a1fe898b7030851b5e22a0d7b3b902ff52f7c03d072a56
predictions_sha256 =
  daf11646f941d0b0f4772d5388bbc6e3abf3e387949e982df02a8241436f2ea2
```

Baseline smoke metrics:

| Metric | @1 | @3 | @5 |
|---|---:|---:|---:|
| Essential macro recall | 0.6667 | 1.0000 | 1.0000 |
| Relevant macro recall | 0.4167 | 1.0000 | 1.0000 |
| Relevant hit rate | 0.6667 | 1.0000 | 1.0000 |
| Known invalids per judged query | 0.0000 | 0.1667 | 0.1667 |
| Invalid rate among judged predictions | 0.0000 | 0.0833 | 0.0833 |

Mean reciprocal rank was `0.8333`. These values are regression fixtures, not
evidence that the baseline is useful on real thoughts.

### Diagnosed issue and fix

The first isolated run exposed a G0 portability defect: dataset and config
fingerprints hashed raw text bytes, so a CRLF checkout/archive could produce a
different hash from an LF checkout of the same logical files. Rankings were
deterministic and the original nine tests passed, but cross-checkout provenance
was not.

The fix:

1. canonicalizes physical text newlines to LF before hashing dataset and config
   inputs;
2. adds a regression test that creates logically identical LF and CRLF datasets
   and requires equal fingerprints;
3. adds `.gitattributes` to keep future repository text files on LF.

The clean validation was rerun after the fix and passed with ten tests. The
initial failure remains recorded here because it is evidence that the clean-copy
check caught a real defect.

### G0 assessment

G0 passes for the current smoke harness:

- schema and label semantics are validated;
- future-directed judgments are rejected as temporal leakage;
- candidate rankings contain only prior thoughts;
- deterministic outputs are reproducible in an isolated copy;
- fingerprints are independent of physical LF/CRLF checkout style;
- paid execution requires explicit gates and the smoke run spends nothing;
- commands and stable output identifiers are recorded.

This does **not** establish generic retrieval quality, personal associative
fidelity, graph value, downstream utility, or generalization.

### Remaining validation limits

- The isolated run used Windows and Python 3.14.2; CI across the minimum
  supported Python 3.12 and another operating system remains future work.
- No external dataset adapter, embedding model, LLM, personal data, or graph
  algorithm exists yet.
- Runtime is intentionally measured rather than deterministic.
