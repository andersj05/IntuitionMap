# IntuitionMap

IntuitionMap is an experimental personal intuition graph: a system for capturing
unfinished thoughts, proposing attributable relationships between them, and
retrieving useful regions of that graph for later reasoning.

The repository currently begins with the evaluation harness because the linking
system is the central research risk.

## Research program

The canonical [research and implementation
plan](docs/research-and-implementation-plan.md) defines the scientific target,
public-data acquisition strategy, label-efficient personal-data path, baseline
ladder, evaluation gates, implementation phases, and handoff instructions for
future agents.

Its central constraint is that public benchmarks can validate generic memory,
personalization, and relationship-learning capabilities, but only protected
user judgments can establish that the system predicts a user's intuition.

Phase 0 research controls:

- [literature matrix](docs/literature-matrix.md)
- [dataset registry](docs/dataset-registry.md)
- [experiment card template](docs/experiment-template.md)
- [decision and result log](docs/decision-log.md)
- [validation record](docs/validation-record.md)

## Evaluation harness

The first benchmark measures temporal edge-candidate retrieval:

> Given a newly captured thought, can a linker retrieve earlier thoughts that a
> human marked as essential or valid connections without repeatedly surfacing
> known-invalid connections?

Run the deterministic, offline smoke experiment:

```powershell
$env:PYTHONPATH = "src"
python -m intuition_map_eval validate --dataset datasets/smoke
python -m intuition_map_eval run `
  --dataset datasets/smoke `
  --config configs/lexical-baseline.json
python -m unittest discover -s tests -v
```

These commands make no API requests. Paid model runs will require both an
explicit configuration switch and an explicit CLI flag, and will be rejected if
their worst-case projected cost exceeds the run budget.

See [docs/evaluation-harness.md](docs/evaluation-harness.md) for the research
contract, labeling rules, metrics, spend controls, and roadmap.
