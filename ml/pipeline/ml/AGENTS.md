# HeatIQ ML Instructions

These instructions apply to everything under `ml/`.

Also follow the root `AGENTS.md`.

## ML Ownership

The ML side owns:

- ML-specific preprocessing
- exploratory analysis
- feature engineering
- lag features
- rolling features
- target construction
- chronological train/validation/test splitting
- model training and evaluation
- XGBoost baseline/primary model
- lightweight GRU experiment only if useful
- inference interface
- heat-health risk logic
- model explainability
- recommendation engine

The ML side does NOT own the backend's deterministic thermal formulas
or FastAPI implementation unless explicitly asked.

Do not duplicate Heat Index / UTCI / WBGT implementations already
owned by the backend/thermal layer.

## Current ML Goal

The immediate prototype objective is NOT mortality prediction.

The current ML development path is:

historical weather
    ->
canonical weather features
    ->
temporal feature engineering
    ->
thermal-hazard prediction baseline
    ->
heat-health risk combination
    ->
recommendation engine

The prototype should support a future 1–5 day horizon.

The current baseline model preference is XGBoost because the data is
primarily structured/tabular and compute is limited.

Do not add GRU/deep learning until a simpler baseline exists and is
evaluated.

## Current ERA5 Work

Historical weather exploration currently uses ERA5-Land NetCDF data.

Observed raw variables include:

- `t2m` - 2m temperature, K
- `d2m` - 2m dewpoint temperature, K
- `sp` - surface pressure, Pa
- `ssrd` - downward solar radiation, J m^-2
- `strd` - downward thermal radiation, J m^-2
- `u10` - 10m U wind component, m s^-1
- `v10` - 10m V wind component, m s^-1

Initial canonical variables are:

- `temperature_c`
- `dewpoint_c`
- `relative_humidity_pct`
- `wind_speed_ms`
- `surface_pressure_pa`
- `solar_radiation_wm2`
- `thermal_radiation_wm2`

Current exploratory area is around Bhubaneswar.

Do not assume exploratory sample dates represent the final training
period.

## Preprocessing Rules

Preprocessing should evolve from notebook exploration into reusable
functions under `ml/preprocessing/`.

Prefer functions with single responsibilities, for example:

- load/merge ERA5 files
- derive canonical weather variables
- validate weather data
- select geographic point/region

Do not turn notebooks into production modules.

Do not modify raw NetCDF files.

Keep raw ERA5 variable names separate from canonical HeatIQ names.

Preserve scientific metadata/units where practical.

Tiny negative solar-radiation artifacts may be clamped to zero only
in the derived canonical variable, never in the raw variable.

Radiation conversion semantics must be documented/verified before
being treated as finalized production logic.

## Validation Expectations

For preprocessing, check at minimum:

- expected variables exist
- expected dimensions are compatible
- missing-value count
- temperature plausibility
- RH roughly in [0, 100]
- wind speed >= 0
- solar radiation >= 0 after cleaning
- timestamps are ordered
- output units are documented

Raise an explicit error for incompatible required inputs rather than
silently producing bad data.

## ML Evaluation

Do not randomly shuffle time-dependent observations when it creates
temporal leakage.

Use chronological splits.

Establish a simple baseline before XGBoost.

Record appropriate metrics.

Do not optimize against the test set.

## Recommendations

Initial recommendations should be deterministic and explainable.

Recommendations must be based on documented:

- risk level
- hazard characteristics
- vulnerability/exposure
- adaptive capacity/resources

Every recommendation should expose reason codes.

Do not use an LLM as the source of public-health policy logic.