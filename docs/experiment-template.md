# IntuitionMap experiment card template

Copy this file for every nontrivial model, metric, split, graph, data, prompt, or
paid-inference change. Complete and lock the preregistration section **before**
implementation or execution. Append results; do not rewrite the preregistered
decision rule after seeing protected-test outcomes.

Suggested ID: `EXP-YYYY-NNN-short-name`.

## Status

```yaml
id:
title:
status: draft # draft | locked | running | complete | invalid
owner:
created_at:
locked_at:
completed_at:
research_question: # RQ1-RQ8 from the canonical plan
claim_level: # C1-C5
gate: # G0-G7
```

## Preregistration

```yaml
hypothesis:
decision_this_can_change:
intervention:
strongest_comparable_baseline:

datasets:
  - registry_id:
    exact_version:
    manifest_sha256:
    allowed_use_confirmed: false
    native_task_preserved: true
dataset_versions_and_hashes:
train_dev_test_time_boundaries:
split_manifest_sha256:
protected_test_access_policy:

information_available_to_each_system:
  intervention:
  baseline:
candidate_pool:
top_k:

primary_metric:
secondary_metrics:
practical_minimum_effect:
statistical_test_and_interval:
number_of_seeds_or_repeats:
fixed_seeds:

invalid_exposure_tolerance:
abstention_policy:
calibration_method:

latency_budget:
token_budget:
max_cost_usd:
allow_paid_api: false
max_paid_retries: 0
model_and_pricing_snapshot:

privacy_risks:
external_service_data_flow:
retention_and_deletion_behavior:
expected_failure_modes:
stop_go_rule:
```

## Preregistration checklist

- [ ] The experiment can change a named decision.
- [ ] One primary metric and a practical minimum effect are locked.
- [ ] The strongest cheaper baseline receives the same candidate pool,
  information, and budget.
- [ ] Train/dev/test boundaries are chronological and queries stay together.
- [ ] Dataset IDs, exact versions, manifests, terms, and allowed uses are in
  [the registry](dataset-registry.md).
- [ ] Unlabeled pairs remain unknown; only explicit `invalid` labels are
  negative.
- [ ] Discovery and proposal streams, exposure source, and sampling probability
  remain distinguishable.
- [ ] Hyperparameters, thresholds, seeds, prompts, and graph statistics are
  fit without protected-test information.
- [ ] Paid calls, if any, require both spend gates and a worst-case preflight
  below `max_cost_usd`.
- [ ] Private data remains local unless a separately recorded consent explicitly
  permits a named service and purpose.
- [ ] The result will not be described above its claim level.

## Implementation record

Complete before the first run:

```yaml
implementation_commit:
config_path:
config_sha256:
split_manifest_path:
split_manifest_sha256:
environment:
  os:
  python:
  dependency_lock_sha256:
models:
  - role:
    provider:
    exact_identifier:
    revision_or_snapshot:
    local_or_remote:
prompts:
  - role:
    path:
    sha256:
indexes_and_caches:
  - role:
    key:
    build_inputs_sha256:
leakage_checks:
budget_preflight:
```

## Results

Append one record per completed run. Keep raw artifacts immutable.

```yaml
run_id:
started_at:
completed_at:
source_commit:
source_dirty: false
resolved_config_sha256:
dataset_manifest_sha256:
split_manifest_sha256:
raw_artifact_path:
raw_artifact_sha256:

primary_result:
baseline_result:
absolute_effect:
relative_effect:
confidence_interval:
statistical_test_result:

secondary_results:
invalid_exposure:
abstention_rate:
calibration:
subgroup_results:
run_to_run_variance:

latency:
tokens:
actual_cost_usd:
paid_api_request_count:

failures_by_taxonomy:
unexpected_failures:
privacy_or_provenance_incidents:
```

## Interpretation and decision

```yaml
result_scope:
supports_hypothesis: # yes | no | mixed | invalid
stop_go_rule_outcome: # stop | revise | advance | invalid
claim_allowed:
claim_not_allowed:
failure_analysis:
decision:
decision_log_entry:
follow_up_experiment:
```

Questions to answer in prose:

1. Did the intervention beat the strongest comparable baseline by the locked
   practical effect, with the planned uncertainty interval?
2. Was any gain purchased with higher invalid exposure, lower coverage,
   leakage, provenance error, latency, tokens, or money?
3. Which query/relation/time subgroups failed, and were those subgroups named
   before the protected result was opened?
4. What is the simplest competing explanation for the result?
5. What evidence would falsify the chosen interpretation?

## Invalid-run conditions

Mark the run `invalid`, preserve its artifacts, and do not use it for a gate if
any of these occur:

- future information, protected feedback, or test-derived graph statistics
  enter training/tuning;
- source and target direction is reversed;
- dataset/version/config/prompt/model identifiers cannot be reconstructed;
- an acquired artifact lacks compatible recorded terms;
- private content crosses an unconsented service boundary;
- paid execution bypasses either spend gate or exceeds the cap;
- intervention and baseline receive materially different candidate pools or
  information without preregistration;
- metrics or the stop/go threshold are changed after opening the protected
  result.
