# Private data and consent policy

**Policy version:** 0.1.0

**Status:** applies before the first real import

This policy governs the single-user IntuitionMap pilot. It is an engineering
and research control, not a substitute for legal, medical, or institutional
privacy review.

## Consent is required before import

The importer rejects a participant unless the local store contains an active,
versioned consent receipt that covers:

- the exact participant pseudonym;
- each source type being imported;
- `local_retrieval_research`, `annotation_pilot`, or both;
- whether raw source text may be stored;
- whether derived features may be created;
- whether local training use is permitted;
- a positive retention period;
- local-only processing;
- four explicit acknowledgements:
  ownership/control of the content, sensitive-data risk, deletion limits, and
  the absence of application-level encryption.

Consent is scoped, content-addressed, and never inferred from providing a file.
An expired or revoked receipt blocks new import, annotation, and training
processing. Revocation does not silently delete data; export and deletion
remain separate user-controlled actions.

## Data requested for the pilot

The first importer accepts UTF-8 JSON Lines. Each record has this form:

```json
{
  "source_type": "note",
  "source_id": "stable-id-from-the-source",
  "source_version": "1",
  "captured_at": "2026-01-01T09:00:00Z",
  "text": "Exact source text",
  "contexts": ["optional-user-created-tag"],
  "explicit_links": ["earlier-source-id"],
  "provenance": {
    "optional": "source-owned metadata"
  }
}
```

`source_type`, `source_id`, `source_version`, `captured_at`, and `text` are
required. Timestamps require a timezone. Contexts, explicit links, and
provenance are optional. One file must contain one source type.

Do not include content the user does not own or control. Consider removing
passwords, access tokens, financial account data, government identifiers,
medical details, legal material, and third-party private information before
import even though a derived redaction pass exists.

## Local storage and service boundary

The workflow makes no API calls. Private content is not sent to OpenAI or any
other hosted service. The existing OpenAI key is not read by this workflow.
All retrieval used to assemble the pilot queue is deterministic and local.

An in-repository workspace is allowed only below ignored
`datasets/private/`. A workspace outside Git is also allowed. The store uses
SQLite with foreign keys, `secure_delete`, a non-WAL journal, restrictive file
permissions where supported, and content hashes.

Local-only is not equivalent to encrypted:

- there is no application-level database encryption in policy version 0.1.0;
- operating-system account security and full-disk encryption are recommended;
- malware, administrators, filesystem snapshots, swap, and device forensics
  remain outside the application's guarantees.

No private data, database, batch, response, or export may be committed to Git.
The committed test fixture is explicitly fictional.

## Immutable source and derived redaction

The source key is `(participant, source_type, source_id, source_version)`.
Re-importing identical content is idempotent. Reusing that key with changed
text, timestamp, links, contexts, or provenance is rejected. A genuine edit
must use a new source version.

When raw storage is consented, exact source text is retained locally. A
separate derived redacted view masks obvious email addresses, phone numbers,
US Social Security number patterns, and OpenAI-style API key patterns. Match
hashes and the redaction-ruleset version are recorded. Redaction never rewrites
the immutable source.

When exact raw storage is declined, the store retains the content hash and the
derived-redacted view, not the exact raw field. This is still not a hash-only
system: the redacted view contains most original language and remains private.

The redactor is deliberately conservative and incomplete. It cannot reliably
identify names, addresses, health information, project secrets, contextual
identifiers, or every credential format. Redacted output must still be treated
as private.

## Labels and exposure

Explicit source links become weak positive labels with provenance and
confidence. They never overwrite or masquerade as gold judgments. Missing
links remain unknown.

The annotation workflow has two stages:

1. A discovery prompt shows the new thought but no proposed candidate. The
   user may independently identify any earlier essential thought or submit an
   empty response.
2. Only after that discovery response is stored can the system create up to
   five proposals: two TF-IDF results, one TF-IDF/BM25 disagreement, one
   deterministic diversity result, and one probability-logged temporal random
   sample.

Proposal exports ask for one of `essential`, `valid`, `invalid`, or
`uncertain`. Relation types and rationale are optional. The store records
sampling source, selection probability, exposure, response time, and stream,
but selection and blind-repeat identity are omitted from the user-facing
batch.

Completed proposal judgments can be resampled at no more than ten percent
after a declared delay. Repeat judgments are new observations; no response or
gold judgment can be overwritten.

## Protected chronological test

After import and before proposal collection, the workflow seals the last
chronological query block in a content-addressed manifest. Query IDs remain
together. Further imports are blocked for that pilot, and training exports
exclude protected query thoughts and all protected-test judgments.

The protected test can still be labeled for final evaluation, but its results
must not influence model choice, thresholds, queue construction, or training.

## Export

Every managed export must remain inside the private workspace and is tracked
for deletion.

- The default portability export uses derived-redacted thought text.
- A raw portability export requires an explicit `--include-raw` action.
- Training export requires active training consent, never includes raw text,
  hashes source IDs, removes source provenance, and excludes the protected
  chronological test.
- Consent receipts are included only in the user's portability export.

Redacted exports can still contain sensitive metadata, identifiers, relation
types, or imperfectly redacted rationales. They are private artifacts, not
publication-ready datasets.

## Retention, revocation, and deletion

The receipt's retention period blocks new processing after expiry. Version
0.1.0 does not run a background deletion daemon; the user must explicitly
export or delete before the deadline.

Participant deletion:

- deletes the participant row and cascades through consent, imports, thoughts,
  explicit links, weak labels, split manifests, queues, responses, judgments,
  and export records;
- removes each exact managed batch, response, and export file still present;
- enables SQLite secure deletion and runs `VACUUM`;
- retains only content-free audit events keyed by a participant hash.

Deletion does **not** remove:

- the user's original source files;
- files copied outside the managed workspace;
- operating-system, cloud, or Git backups;
- filesystem snapshots or forensic remnants that the operating system or
  storage device retains.

The deletion receipt states these limits. The user must separately remove
originals and backups when desired.

## Pilot gate

The preregistered [`EXP-P3-001`](../configs/experiments/EXP-P3-001-private-workflow-pilot.yaml)
requires at least 100 completed proposal responses, 20 discovery responses,
and 10 comparable blind repeats. Median proposal time must be at most ten
seconds, completion at least 80%, and repeat agreement at least 70%.

The automated burden report can never self-certify G3. Provenance,
chronology, private-content escape, and deletion audits must also pass with
zero failures before collection expands.
