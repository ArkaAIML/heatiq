# HeatIQ Backend

> **SIH26083 \| Human Thermal Stress & Health Risk Early Warning
> Platform**

HeatIQ is a backend pipeline designed to answer a question that ordinary
weather systems do not:

> **What will the current atmospheric conditions do to people in
> different wards?**

The backend takes a geographic location, acquires atmospheric
conditions, computes thermal stress, combines that with ward-specific
demographic/resource context, runs prediction and mortality components,
filters wards by risk, stores the resulting ward context, and can later
generate a recommendation for a specifically requested ward.

The system is deliberately split into two flows:

-   **Wire 1:** full location-to-ward-risk processing
-   **Wire 2:** on-demand recommendation for one already-processed ward

The final **Main Gate** will wrap these two flows. It is not part of the
current implementation checkpoint.

------------------------------------------------------------------------

## 1. What the Backend Does

At a high level:

``` text
                    LOCATION
                       |
                       v
                    Wire 1
                       |
          +------------+-------------+
          |                          |
          v                          v
 Atmospheric Data                Data Lake
 Acquisition                  Info / Resource
          |                     Pool data
          v                          |
    Thermal Engine                  |
          |                          |
          v                          |
    Prediction ML                   |
          |                          |
          v                          |
       Mortality <------------------+
          |
          v
      Ward Filter
          |
          v
   Ward Context Store
          |
          |
          |       later, when requested
          |                  |
          |                  v
          +-----------> Wire 2
                             |
                             v
                    Recommendation Engine
                             |
                             v
                    RecommendationOutput
```

The important architectural idea is that **Wire 1 performs the expensive
full pipeline once**, stores the resulting ward context, and **Wire 2
does not recompute the entire pipeline** when a government-dashboard
user requests a recommendation for a particular ward.

------------------------------------------------------------------------

# 2. The Two Wires

## Wire 1: Full System Flow

Wire 1 accepts a location such as:

``` text
Bhubaneswar
```

and processes the complete system.

``` text
Bhubaneswar
    |
    v
Atmospheric Data Acquisition
    |
    v
Thermal Engine
    |
    v
Prediction
    |
    v
Mortality
    |
    v
Ward Filter
    |
    v
Ward Context Store
```

The resulting context is retained by `area_id` for every processed ward.

### What Wire 1 is responsible for

Wire 1 is an **orchestrator**.

It connects modules.

It does **not**:

-   implement thermal mathematics,
-   implement mortality mathematics,
-   implement Ward Filter rules,
-   implement ML algorithms,
-   parse arbitrary external datasets itself,
-   or become another business-logic engine.

Its job is to move correctly structured information between the existing
module boundaries.

------------------------------------------------------------------------

# 3. Atmospheric Data Acquisition

The atmospheric acquisition component exists inside the Thermal Engine's
boundary, immediately before the Thermal Gateway.

Its job is:

``` text
location
   |
   v
weather provider
   |
   v
raw atmospheric response
   |
   v
normalization
   |
   v
ThermalInput
```

The current real atmospheric provider path uses **Open-Meteo**.

The provider-specific logic is isolated so that the Thermal Engine does
not need to know how the weather data was obtained.

A mock provider is retained for deterministic testing.

## Current geographic resolution

The current architecture intentionally uses **location/city-level
atmospheric observations**.

For example:

``` text
Bhubaneswar atmospheric condition
              |
              v
        Thermal Engine
              |
              v
       common thermal hazard
              |
       +------+------+
       |      |      |
       v      v      v
    Ward 1  Ward 2  Ward 3
       |      |      |
       +------+------+
              |
              v
    ward-specific context
              |
              v
         Ward Filter
```

The system therefore does **not** currently require an independent
weather measurement for every ward.

The distinction is intentional:

-   Thermal Engine determines the environmental thermal condition.
-   Downstream ward-level processing determines how that condition
    affects a particular ward.

------------------------------------------------------------------------

# 4. Thermal Engine

The Thermal Engine receives normalized atmospheric data through its
gateway.

Conceptually:

``` text
ThermalInput
    |
    v
Thermal Gateway
    |
    v
thermal calculations
    |
    v
ThermalOutput
```

The Thermal Engine is responsible for the thermal mathematics.

Depending on the configured calculation set, its output contains the
canonical thermal indicators used by the rest of the backend.

The orchestration layer does not duplicate these calculations.

------------------------------------------------------------------------

# 5. Prediction Engine

Prediction is an ML boundary.

Its conceptual role is:

``` text
ThermalOutput
      |
      v
Prediction Adapter
      |
      v
Prediction ML
      |
      v
PredictionOutput
```

The Prediction Engine is responsible for prediction.

It is **not** responsible for:

-   mortality calculation,
-   Ward Filter classification,
-   recommendations,
-   or orchestration.

The current repository retains `dummyML` as a controlled
prototype/testing boundary. The actual external ML model can replace
this boundary without requiring the whole backend architecture to be
rewritten.

------------------------------------------------------------------------

# 6. Mortality

The Mortality component combines the relevant thermal and human/resource
context according to its canonical contract.

Conceptually:

``` text
Thermal context
       +
Info Pool
       +
Resource Pool
       |
       v
   Mortality
       |
       v
mortality result
```

Mortality is a separate computational responsibility.

The wiring layer does not recreate its calculations.

------------------------------------------------------------------------

# 7. Data Lake

The Data Lake provides structured contextual information to the
pipeline.

It is conceptually divided into:

``` text
Data Lake
   |
   +---- Info Pool
   |
   +---- Resource Pool
```

These pools represent different kinds of information and remain separate
canonical concepts.

The Data Lake is where external structured datasets are converted into
the canonical records expected by the rest of HeatIQ.

------------------------------------------------------------------------

# 8. Parser Layer

The parser layer exists at the Data Lake boundary.

Its purpose is to absorb differences between real-world datasets and the
canonical HeatIQ schemas.

The backend currently supports/test-covers common structured formats
such as:

-   CSV
-   TSV
-   JSON
-   NDJSON / JSON Lines
-   XLSX
-   Parquet
-   ZIP archives containing supported structured files

The parser handles issues such as:

-   inconsistent header capitalization,
-   common header naming variations,
-   null/missing values,
-   nullable integer fields,
-   numeric normalization,
-   timestamps,
-   area identifiers,
-   geographic scope,
-   schema validation,
-   partial record failures,
-   source-specific mappings,
-   and provenance where available.

The parser should **not** silently convert bad data into plausible data.

For example:

``` text
missing population
```

must not automatically become:

``` text
population = 0
```

Likewise, a ward-level field must not silently be populated with a
district-level value merely because both columns happen to be named
`population`.

------------------------------------------------------------------------

# 9. Area IDs

`area_id` is one of the most important pieces of identity in the
backend.

The system uses it to preserve ward identity through the pipeline.

Conceptually:

``` text
WARD_001
    |
    v
Info / Resource context
    |
    v
Thermal
    |
    v
Prediction
    |
    v
Mortality
    |
    v
Ward Filter
    |
    v
Ward Context Store
    |
    v
Wire 2
```

The backend must never rely on:

-   list position,
-   processing order,
-   "last processed ward",
-   or population values

to identify a ward.

If Wire 2 requests:

``` text
WARD_002
```

it must retrieve the context belonging to:

``` text
WARD_002
```

and not another ward.

------------------------------------------------------------------------

# 10. Ward Filter

The Ward Filter is responsible for deterministic ward-level risk
filtering.

It takes the relevant ward context and applies the configured rules to
determine the ward's resulting risk/severity state.

Conceptually:

``` text
ThermalOutput
PredictionOutput
Mortality result
Info Pool context
Resource Pool context
        |
        v
    Ward Filter
        |
        v
ward-level filtered result
```

The Ward Filter does not replace the ML models.

Likewise, ML models do not replace the Ward Filter's deterministic
filtering responsibility.

------------------------------------------------------------------------

# 11. Ward Context Store

The Ward Context Store is the bridge between Wire 1 and Wire 2.

After Wire 1 completes:

``` text
Ward Filter
    |
    v
Ward Context Store
```

The store retains the final context associated with each `area_id`.

This prevents Wire 2 from having to recompute the entire backend.

For example:

``` text
Wire 1
  |
  +--> WARD_001 context
  +--> WARD_002 context
  +--> WARD_003 context
```

Later:

``` text
Wire 2("WARD_002")
       |
       v
Ward Context Store
       |
       v
WARD_002 context only
```

This is also what allows a government dashboard to request a
recommendation for a specific ward without triggering a full Bhubaneswar
recomputation.

------------------------------------------------------------------------

# 12. Wire 2: Recommendation Flow

Wire 2 accepts an `area_id`.

Example:

``` text
WARD_001
```

The intended flow is:

``` text
area_id
   |
   v
Wire 2
   |
   v
Ward Context Store
   |
   v
exact WardContext
   |
   v
Recommendation Adapter
   |
   v
Recommendation ML
   |
   v
RecommendationOutput
   |
   v
Wire 2 caller
```

Wire 2 must not rerun:

``` text
Atmospheric Acquisition
Thermal
Prediction
Mortality
Ward Filter
```

The stored context is the input to the recommendation stage.

------------------------------------------------------------------------

# 13. Recommendation Engine

The Recommendation Engine is an ML component owned separately from the
core deterministic backend logic.

Its conceptual responsibility is:

> Given the already-computed context of a particular ward, determine the
> appropriate recommendation.

It is therefore different from Prediction.

### Prediction

``` text
"What is likely to happen?"
```

### Recommendation

``` text
"What should be recommended for this ward?"
```

They have similar integration shapes but different responsibilities and
contracts.

The actual Recommendation ML model is not yet integrated.

The current dummy boundary may return an explicit result such as:

``` json
{
  "status": "DUMMY",
  "priority": "UNKNOWN",
  "actions": [],
  "reason_codes": []
}
```

This is intentional.

A dummy/unavailable recommendation is preferable to fabricated advice.

The actual model's input/output contract must be supplied by the model
owner before the dummy compatibility path is replaced.

------------------------------------------------------------------------

# 14. Why the Current Terminal Output Says `DUMMY`

A live backend run can currently reach Wire 2 and produce a result
similar to:

``` json
{
  "area_id": "WARD_001",
  "priority": "UNKNOWN",
  "actions": [],
  "reason_codes": [],
  "status": "DUMMY",
  "message": "Recommendation engine unavailable..."
}
```

This does **not** mean the whole backend is dummy.

It means the current Recommendation ML boundary is still a
dummy/unavailable implementation.

The thermal calculations occur earlier:

``` text
Atmospheric API
      |
      v
ThermalInput
      |
      v
Thermal Engine
      |
      v
ThermalOutput
```

The current diagnostic runner simply does not print every field from the
ThermalOutput.

The correct future behavior is:

``` text
actual ThermalOutput
       |
       v
diagnostic serializer
       |
       v
terminal
```

not manually inserting fake heat-index numbers into the terminal output.

------------------------------------------------------------------------

# 15. What Is Real Right Now?

The current backend contains real implementations for major non-ML
processing boundaries, including:

-   atmospheric acquisition through the current real provider path,
-   Thermal Engine execution,
-   Data Lake parsing,
-   ward context handling,
-   Mortality integration,
-   Ward Filter integration,
-   Wire 1,
-   Wire 2,
-   and Ward Context Store behavior.

The current system also retains controlled prototype components where
final external data/models are not yet available.

------------------------------------------------------------------------

# 16. What Is Still Temporary?

The following are intentionally not final:

  Component                 Current state
  ------------------------- ---------------------------------
  Atmospheric acquisition   Real provider boundary
  Thermal Engine            Real
  Prediction                Dummy ML boundary currently
  Recommendation            Dummy/external contract pending
  Demographic data          Controlled prototype data
  Resource data             Controlled prototype data
  Main Gate                 Not implemented yet
  Real Bhubaneswar Census   Deferred

The presence of `dummyML` is intentional and does not mean the
surrounding architecture is fake.

------------------------------------------------------------------------

# 17. Main Gate

The final public backend wrapper has not yet been implemented.

Its intended role is to provide one coherent external entry point:

``` text
                    MAIN GATE
                   /         \
                  /           \
            location          area_id
                |                |
                v                v
              Wire 1           Wire 2
                |                |
                v                v
         full processing    recommendation
```

The Main Gate should remain thin.

It should route requests into the appropriate wire and return structured
results.

It should not become another business-logic layer.

------------------------------------------------------------------------

# 18. Error Handling

The backend is designed to distinguish valid results from unavailable or
failed results.

Important principles include:

-   do not fabricate missing atmospheric data,
-   do not silently convert invalid values to zero,
-   do not silently turn failures into `NORMAL`,
-   preserve ward identity where possible,
-   isolate partial ward failures,
-   and distinguish source-level failure from individual bad records.

For example:

``` text
WARD_001 → valid
WARD_002 → insufficient data
WARD_003 → valid
```

should not become:

``` text
all wards → failed
```

merely because WARD_002 failed.

------------------------------------------------------------------------

# 19. Testing Strategy

Testing has intentionally been performed in multiple layers.

``` text
Unit tests
    ↓
Module integration tests
    ↓
Wiring tests
    ↓
Cross-ward tests
    ↓
Failure tests
    ↓
Full backend integration
    ↓
Live-provider execution
    ↓
Final black-box E2E
```

Important integration checks include:

### Area isolation

``` text
WARD_001 ≠ WARD_002 ≠ WARD_003
```

Distinct ward contexts must remain distinct.

### No recomputation

Wire 2 should retrieve stored context instead of rerunning the full
pipeline.

### Data continuity

Values must survive:

``` text
source
 → canonical schema
 → module
 → next module
 → Ward Context Store
 → Wire 2
```

### Failure isolation

A bad ward should not automatically corrupt unrelated wards.

------------------------------------------------------------------------

# 20. Current Known Findings

The cumulative audit currently contains these significant open/partial
items:

### F-010 --- Recommendation ML contract

**OPEN**

The real Recommendation model contract is still external/pending.

### F-011 --- Freshness semantics

**PARTIALLY RESOLVED**

Freshness metadata exists, but the final policy has not been finalized.

### F-012 --- dummyML schema limitation

**PARTIALLY RESOLVED**

The dummy models remain prototype boundaries.

### F-020 --- Real Bhubaneswar demographic data

**OPEN / DEFERRED**

Real ward-level demographic/Census data has not yet been integrated.

### F-022 --- Prediction failure representation

**INFORMATIONAL**

Prediction and Recommendation currently represent failures differently.

### F-021 --- Atmospheric spatial resolution

**ACCEPTED ARCHITECTURAL DECISION**

City/location-level atmospheric input is intentional.

### F-014 --- Nullable demographic integer handling

**RESOLVED**

Parser behavior prevents accidental integer-to-float conversion caused
by missing values.

------------------------------------------------------------------------

# 21. Current Roadmap

``` text
REWIRE
  ✅

PHASE 1  ML boundaries
  ✅

PHASE 2  Ward Context Store
  ✅

PHASE 3  Intelligent Filtering
  ✅

PHASE 4  Failure handling
  ✅

PHASE 5  Real Census + Resource data
  ⏸️ DEFERRED
  └── F-020 open

PHASE 6  Real atmospheric API
  ✅

PHASE 7  Recommendation integration
  🟡 PARTIAL
  └── F-010 external ML contract pending

PHASE 8  Parser robustness
  ✅

PHASE 9  Full integration validation
  ✅

PHASE 10 Main Gate
  🔵 NEXT

PHASE 11 Final black-box E2E
  ⏳

THEN
  ↩︎ return to Phase 5
  real Census integration
```

------------------------------------------------------------------------

# 22. Current Backend Run

The backend can already be exercised without a frontend.

The integration runner can execute the full pipeline for a location and
then request a recommendation for a selected ward.

The important distinction is that the current terminal output is
primarily an integration diagnostic.

It is not yet the final public API/interface.

A future diagnostic run should expose the actual calculated thermal
values, for example:

``` text
============================================================
HEATIQ BACKEND RUN
Location: Bhubaneswar
============================================================

Ward: WARD_001

Atmospheric:
    observation_timestamp: ...

Thermal:
    <actual canonical thermal fields>

Prediction:
    <actual prediction/dummy status>

Mortality:
    <actual mortality fields>

Ward Filter:
    <actual filtered result>

Freshness:
    <actual timestamps>

============================================================
```

The exact field names should always come from the canonical repository
schemas.

------------------------------------------------------------------------

# 23. Design Principles

## Thin orchestration

Wiring connects modules. It does not become a second calculation engine.

## Canonical contracts

Data crossing module boundaries should use explicit canonical schemas.

## Area-ID identity

Ward identity is explicit and preserved throughout the pipeline.

## Fail honestly

Missing data and unavailable ML models must not become fake valid
results.

## Separate deterministic and ML responsibilities

Thermal, Mortality, and Ward Filter have defined computational roles.
Prediction and Recommendation are ML boundaries.

## Store before recommending

Wire 1 computes and stores the ward context.

Wire 2 retrieves the context and performs recommendation on demand.

## Source-specific parsing stays at the Data Lake boundary

The rest of the backend should not care whether a dataset came from CSV,
JSON, Excel, or Parquet.

## Real data replaces fixtures, not architecture

Prototype datasets/models are temporary inputs to stable boundaries.

------------------------------------------------------------------------

# 24. Definition of the Backend

The backend can be summarized as:

``` text
LOCATION
   ↓
ATMOSPHERIC CONDITIONS
   ↓
THERMAL STRESS
   ↓
PREDICTION
   ↓
MORTALITY / HUMAN CONTEXT
   ↓
WARD FILTER
   ↓
WARD-SPECIFIC RISK CONTEXT
   ↓
STORE
   ↓
ON-DEMAND RECOMMENDATION
```

The fundamental idea is:

> **The weather is not the final answer. The backend translates
> environmental conditions into human-impact intelligence at ward
> level.**

------------------------------------------------------------------------

# 25. Current Completion State

The backend is currently at a **pre-final-integration checkpoint**.

The architecture and major data-flow paths have been implemented and
repeatedly audited.

The remaining major milestones are:

1.  Implement Main Gate.
2.  Expose complete canonical thermal output in the diagnostic runner.
3.  Perform final black-box E2E testing.
4.  Integrate legitimate Bhubaneswar demographic data.
5.  Integrate final Recommendation ML contract.
6.  Revalidate the complete pipeline.
7.  Remove only the temporary components that are actually replaceable,
    while retaining `dummyML` until its real models are available.
8.  Connect the eventual frontend to the finished backend.

Until these are complete, the backend should be described as an
integrated prototype/pre-final backend rather than a finished production
system.
