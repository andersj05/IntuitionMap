# Phase 3 private workflow — pre-pilot implementation

**Status:** implementation complete; real pilot and G3 pending user input

**External spend:** 0 paid requests, 0 tokens, $0

## What is ready

The local `intuition_map_private` package provides:

- versioned consent receipts, expiry, and revocation;
- a guarded local SQLite workspace under ignored `datasets/private/` or
  outside Git;
- strict JSONL import with immutable source versions and provenance hashes;
- separate exact raw text and derived-redacted views;
- explicit-link resolution into a distinct weak-label table;
- discovery-first and proposal annotation queues;
- one-action verdict response import with optional relation and rationale;
- exposure, sampling source/probability, response time, and stream logging;
- deterministic controlled random/temporal samples;
- delayed blind repeats whose identity is hidden in exported batches;
- sealed chronological test manifests;
- default-redacted portability export, explicit raw export, and
  consent-gated/test-excluding training export;
- consent revocation and participant deletion with exact managed-file cleanup,
  SQLite secure deletion, and `VACUUM`;
- burden, completion, and repeat-agreement reporting with intervals.

The full behavior and limitations are in
[the private-data policy](private-data-policy.md).

## What has not happened

- No real consent receipt exists.
- No user content has been read or imported.
- No protected personal test manifest has been frozen.
- No user annotation response has been collected.
- G3 has not passed.
- No private content has been sent to a hosted model.

The committed fixture under `tests/fixtures/private/` is project-authored,
fictional data.

## Safety invariants exercised by tests

- Import without active scoped consent fails.
- Expired and revoked consent blocks new processing.
- A Git-local workspace outside ignored `datasets/private/` fails.
- Reusing a source version with changed content or metadata fails.
- Raw and redacted text remain distinct.
- Explicit links create weak labels, not gold judgments.
- A protected manifest is sealed and blocks later pilot imports.
- Proposals cannot be created before a discovery response.
- Discovery and proposal judgments remain separate.
- Unknown/future candidate directions are rejected.
- Responses cannot be overwritten.
- Blind-repeat identity is absent from the user-facing batch.
- Training exports exclude the protected test.
- Default export masks synthetic private markers.
- Export paths cannot escape the managed workspace.
- Deletion cascades through private tables, removes tracked artifacts, and
  removes synthetic canary text from the vacuumed database bytes.

Validation used Python 3.12.4. The project installed successfully as editable
version `0.3.0` with pinned `setuptools==75.8.2`; both `intuition-private` and
`intuition-eval` entry points loaded. The full suite passed 57 tests. No API
request or private artifact was involved.

## Intended pilot sequence

These commands are documented for the later consented pilot; they have not
been run on user data.

```powershell
$env:PYTHONPATH = "src"

python -m intuition_map_private.cli init `
  --workspace datasets/private/pilot

python -m intuition_map_private.cli grant-consent `
  --workspace datasets/private/pilot `
  --participant <pseudonym> `
  --purpose local_retrieval_research `
  --purpose annotation_pilot `
  --source-type note `
  --retention-days 365 `
  --store-exact-raw `
  --allow-derived-features `
  --ack-ownership `
  --ack-sensitive-data `
  --ack-deletion-limits `
  --ack-no-app-encryption

python -m intuition_map_private.cli import-jsonl `
  --workspace datasets/private/pilot `
  --participant <pseudonym> `
  --input <consented-jsonl>

python -m intuition_map_private.cli freeze-test `
  --workspace datasets/private/pilot `
  --participant <pseudonym>
```

The pilot then alternates discovery export/response import, proposal
construction/export/response import, and later blind repeats. Batches default
to 20 items and no source gets more than five proposals.

## Boundary requiring user input

The next action is not code or model training. It is a user decision about
consent scope and a small source format:

1. choose a pseudonym;
2. choose which user-owned source type to pilot;
3. decide whether exact raw text may be stored locally;
4. decide whether later local training use is allowed;
5. choose a retention period;
6. provide or create a correctly formatted JSONL pilot file.

Only after those choices should the real workspace be initialized and the
chronological manifest frozen.
