# Data Lake

The Data Lake maintains the system's canonical, locally stored representation of external government information and resource datasets.

## Role of the Data Lake

The Parquet datasets are the persistent canonical storage backing HeatIQ's Info Pool and Resource Pool data. They are not themselves the business-logic modules.

Conceptually:
External Sources → Parsers → Canonical Data Lake → Parquet → Data Lake interface → Future Gateway → Module-specific structured inputs

The backend / Gateway should use the Data Lake interface functions (`get_canonical_info_pool`, `get_canonical_resource_pool`), and should not directly access the filesystem (e.g. `pandas.read_parquet(...)`).

## Geographic Identity

The Data Lake stores files named by the macro geographic cache identifier (e.g., `datalake/data/info/bhubaneswar.parquet`). This filename acts as a cache identifier, not as a single record.

Inside the file, the records represent individual canonical ward identities, differentiated by the `area_id` column (e.g., `WARD_001`, `WARD_002`).
