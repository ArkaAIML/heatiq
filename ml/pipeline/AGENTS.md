# HeatIQ Agent Instructions

## Project

HeatIQ is an SIH prototype for extreme-heat early warning and human
thermal-stress / heat-health risk decision support.

The system should ultimately answer:

"Where is dangerous human thermal stress likely to occur in the next
1–5 days, how serious is the resulting heat-health risk for the exposed
population, and what interventions should be prioritized?"

This is a hackathon prototype with a very short development timeline.
Prefer simple, reliable, testable implementations over unnecessary
complexity.

## Read Before Editing

Before making changes, read:

1. `README.md`
2. `CONTRIBUTING.md`
3. Any more specific `AGENTS.md` governing the files being edited

## Shared Backend/ML Contract

The backend/ML data contract is currently under discussion and has not
yet been approved by all component owners.

Do not assume or invent an authoritative shared schema.

Until the contract is approved:

- keep component interfaces modular
- avoid hardcoding cross-component assumptions
- do not duplicate another component's responsibilities
- identify integration points explicitly
- ask before making decisions that would constrain another component

Once an approved data contract is added to the repository, it becomes
the source of truth for cross-component schemas.

If code and documentation disagree, report the disagreement instead
of silently choosing one.

## Repository Structure

- `backend/` - backend/API and deterministic thermal calculation work
- `frontend/` - application UI
- `ml/` - prediction, ML feature engineering, risk and recommendation work
- `data/raw/` - downloaded source data; never commit large raw datasets
- `data/interim/` - intermediate generated data
- `data/processed/` - model-ready generated data
- `data/sample/` - small shareable test/sample data only
- `docs/` - shared architecture and contracts
- `tests/` - automated tests

## Dependency Management

This repository uses `uv`.

Use:

- `uv sync`
- `uv add <package>`
- `uv add --dev <package>`
- `uv run <command>`

Do NOT introduce a parallel `pip install` / manually-created venv
workflow.

`pyproject.toml` and `uv.lock` are the dependency source of truth.

Do not manually modify `uv.lock`.

## Git Safety

Never:

- push directly to `main`
- force-push `main`
- delete branches without being asked
- run destructive Git commands such as `git reset --hard`
- rewrite existing commit history
- commit `.env`, credentials, API keys, `.venv`, raw climate datasets,
  large generated datasets, or large model artifacts

Work only on the currently checked-out feature branch.

Do not create commits or push unless explicitly asked.

## Approval Required Before Critical Changes

STOP and ask the user before:

- changing project architecture
- changing the shared data contract/schema
- moving or renaming major directories
- changing ownership boundaries between backend and ML
- adding/removing major dependencies
- changing the ML prediction target
- changing risk-score definitions or thresholds
- changing recommendation-policy semantics
- deleting files
- replacing an existing implementation wholesale
- editing files outside the requested task's module when avoidable
- introducing a new framework/database/service
- downloading large datasets
- performing expensive training runs

Small, local implementation changes that follow the agreed design may
proceed after presenting a concise plan.

## Working Protocol

For every non-trivial task:

1. Inspect relevant existing files first.
2. Restate the goal in 1–3 sentences.
3. Identify the files that likely need modification.
4. Give a short implementation plan.
5. Identify any assumptions or conflicts.
6. Ask before any critical change listed above.
7. Implement the smallest useful increment.
8. Run the narrowest relevant tests/checks.
9. If a test fails, investigate before continuing.
10. Report:
   - what changed
   - what was tested
   - what remains
   - any risks/assumptions

Do not make a large batch of unrelated changes in one pass.

## Testing

Test incrementally.

Prefer:

1. unit/sanity checks for the changed function
2. module-level tests
3. broader tests only when needed

Never claim something works without running an appropriate check when
one is available.

Do not hide failing tests.

## Data Principles

Never modify files under `data/raw/`.

Raw data is immutable input.

Derived datasets belong in:

- `data/interim/`
- `data/processed/`

Large datasets should remain gitignored.

Small deterministic fixtures may live in `data/sample/`.

Always document units for scientific variables.

Do not silently impute or fabricate missing data.

## Scientific / Safety Principles

Do not claim clinical or mortality prediction without real validated
health-outcome labels.

Do not present synthetic labels as real observations.

Distinguish:

- thermal hazard
- exposure
- vulnerability
- adaptive capacity
- heat-health risk

Established deterministic thermal calculations should not be replaced
with ML merely for novelty.

## Compute Constraint

Assume development/training must work on:

- normal developer laptops
- free Google Colab

Prefer:

- Pandas / NumPy / Xarray
- XGBoost / scikit-learn
- lightweight models

Avoid unnecessary large neural networks or memory-heavy pipelines.

## Priority

Working end-to-end prototype > architectural perfection.

For the hackathon MVP prioritize:

1. reliable data preprocessing
2. defensible features
3. working baseline prediction
4. heat-health risk output
5. explainable recommendation rules
6. backend integration
