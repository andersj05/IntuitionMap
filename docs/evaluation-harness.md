# IntuitionMap evaluation harness

## Research contract

The first harness exists to falsify weak approaches to linking thoughts. It does
not attempt to prove that a generated graph looks plausible.

The first evaluation question is:

> At the time a new thought is captured, can the system rank earlier thoughts
> that the user considers essential or legitimately related?

Candidate retrieval is evaluated before relationship classification. A
classifier cannot recover an important link that candidate generation never
showed it.

## Unit of evaluation

Each dataset contains:

- immutable thought captures;
- directed judgments from a newer source thought to an older candidate thought;
- a manifest describing annotation scope and dataset provenance.

A judgment has one of four verdicts:

- `essential`: omitting this connection materially damages the map;
- `valid`: the relationship is useful and defensible, but not indispensable;
- `invalid`: the proposed relationship misrepresents the user's intuition;
- `uncertain`: the annotator cannot currently resolve the relationship.

Unlabeled pairs are **unknown**, not negative. On partially annotated datasets,
the harness therefore reports recall and known-invalid rates, not conventional
precision.

`relation_types` are multi-label because a pair can simultaneously be an
analogy, contradiction, dependency, or other relationship. Relationship typing
is a later task and must not be used to conceal poor candidate recall.

## Temporal protocol

For a source thought captured at time `t`, only thoughts captured before `t` are
eligible candidates. Random train/test splitting is prohibited for the primary
benchmark because it allows future information to leak into past graph states.

When learned models are introduced, splits will be chronological:

1. fit or personalize on an earlier prefix;
2. tune thresholds on the next interval;
3. evaluate once on a later held-out interval.

## Initial metrics

The harness reports:

- essential recall at `k`;
- relevant (`essential` or `valid`) macro recall at `k`;
- relevant hit rate at `k`;
- mean reciprocal rank of the first relevant candidate;
- known-invalid predictions per query at `k`;
- invalid rate among judged predictions at `k`;
- query and judgment coverage;
- runtime, token usage, and estimated cost.

Metrics are accompanied by per-query rankings so every aggregate number can be
audited.

## Failure taxonomy

Every qualitative error should be assigned one or more stable codes:

- `MISSED_EXPLICIT`: missed a relationship directly stated by the user;
- `MISSED_ASSOCIATIVE`: missed a defensible cross-concept association;
- `GENERIC_HUB`: linked through a broad concept that connects almost everything;
- `CONTEXT_COLLAPSE`: treated similar words from different projects as one idea;
- `PROVENANCE_INVERSION`: attributed a model inference to the user;
- `DIRECTION_ERROR`: found the pair but reversed a directed relationship;
- `RELATION_ERROR`: selected the wrong relationship type;
- `CONTRADICTION_MISSED`: treated tension as ordinary similarity;
- `TEMPORAL_LEAKAGE`: used information unavailable when the thought was captured;
- `DUPLICATE_INFLATION`: gained apparent recall by creating redundant nodes;
- `GRAPH_SATURATION`: proposed so many weak links that retrieval becomes noisy;
- `OVERLY_SAFE`: found literal matches but no useful distant associations.

## Spend policy

Live model calls are opt-in. The default paid baseline is pinned to
`gpt-5-nano-2025-08-07` with reasoning disabled. The pricing snapshot in
`configs/model-pricing.json` is dated and must be reviewed before paid
experiments if pricing may have changed.

Paid execution will require all of the following:

1. `allow_paid_api` in experiment configuration;
2. an explicit CLI `--allow-paid-api` flag;
3. a worst-case preflight estimate within `max_cost_usd`;
4. a per-request check using remaining budget;
5. zero automatic paid retries by default;
6. actual token usage recorded after each response;
7. content-addressed caching so identical completed calls are not repeated.

The code currently implements the budget ledger and offline runner. A live model
adapter will only be added behind these gates. No smoke test should spend money.

## Dataset tiers

- `datasets/smoke`: synthetic, versioned fixtures for software correctness only;
- `datasets/private`: ignored local data for the developer's own thoughts;
- future consented benchmark: sanitized, versioned data suitable for scientific
  comparisons.

Smoke results are never evidence of product quality.

## Experiment artifacts

Each run writes an immutable directory containing:

- resolved configuration and fingerprints;
- dataset fingerprint;
- source revision and dirty-state metadata when available;
- full ranked predictions;
- aggregate metrics;
- timing and zero-or-more usage ledger entries.

This allows later algorithms to be compared against exactly the same inputs.

## Research sequence

1. Validate deterministic lexical and recency baselines.
2. Freeze the literature, dataset, experiment, decision, and validation
   controls in the canonical research plan.
3. Register only the minimum orthogonal public capability datasets and preserve
   their native evaluation.
4. Strengthen cheap offline retrieval and measurement before adding a paid
   model.
5. Implement consent, local storage, redaction, export, deletion, annotation,
   and protected chronological splits before requesting personal data.
6. Pilot a small hand-labeled private temporal dataset and measure burden and
   label stability.
7. Test a small personal head, then relationship typing and graph traversal as
   matched ablations.
8. Test controlled novelty and downstream utility before considering learned
   memory policies, graph neural networks, or broader intuition claims.
