***
# AETHER CLOUD PLATFORM (ACP) DEVLOG
***
## Repo skeleton and env sanity (2026-03-02)

**Action:** Created the ACP repository skeleton with a strict local-only `data/` directory (gitignored) and a `.env.example` containing only default local credentials and port mappings.

**Decision:** start with a minimal `bootstrap` container in Compose. This intentionally does not include any real services as of now. The purpose is to validate Docker and Compose execution initially, before introducing a multi-service failure surface.

**Tradeoff:** this initial setup doesn’t prove any platform capability yet. It only proves the scaffolding is correct and appropriate for future development.

---

## ACP CLI Foundation (2026-03-02)

### Objective

Establish a command-line interface (`aether` or by `./aether.sh`) to act as the primary control surface for the Aether Cloud Platform.

This transforms ACP from a collection of inconvenient Docker commands into a cohesive platform with a stable and reproducible operational interface.

Instead of interacting with infrastructure directly via:

```bash
docker compose up -d
docker compose down
```

Users interact with ACP via:

```bash
aether up
aether down
aether status
aether doctor
```

This abstraction is intentional. The CLI becomes the platform boundary, and Docker Compose becomes an implementation detail.

---

### Implementation

The CLI was implemented in Python using **Typer**, chosen for:

- clean command structure
- excellent help output
- minimal boilerplate
- easy extensibility for future commands (e.g., `smoke-test`, `submit`, `reset`)

The CLI lives in the `aether/` package and is exposed via a console entrypoint defined in `pyproject.toml`:

```toml
[project.scripts]
aether = "aether.cli:app"
```

Therefore, the CLI may be installed into the environment and executed globally via:

```bash
aether up
```

A Conda environment (`ACP_env`) was used to isolate dependencies and ensure reproducibility.

Editable install in conda environment:

```bash
pip install -e .
```

CLI iteration as a result should be quick and smooth without reinstalling after code changes.

---

#### Packaging issue encountered

Initial installation failed with:

```bash
Multiple top-level packages discovered in a flat-layout
```
**CAUSE:**
The cause of this was due to Setuptools attempting to package the entire repository, including the infrastructure directories (`docker/`, `data/`, etc...), rather than the CLI package exclusively.

**RESOLUTION:**
Explicit package declaration in `pyproject.toml`:

```toml
[tool.setuptools]
packages = ["aether"]
```

This restricted packaging to the intended CLI module.

Since ACP is the initial infrastructure project before building additional project within its architecture, ACP is not a Python library. The CLI is a component of the platform rather than a standalone entity.

---

#### Initial CLI command dictionary 

| Command          | Purpose                                              |
| ---------------- | ---------------------------------------------------- |
| `aether up`      | Starts platform via Docker Compose                   |
| `aether down`    | Stops platform                                       |
| `aether restart` | Clean restart                                        |
| `aether status`  | Shows Compose state                                  |
| `aether doctor`  | Validates Docker, environment, and port availability |


---

#### Verification


Successful tests: 

```bash
aether up
aether status
aether doctor
aether down
```

Confirmed:

- CLI executable available in Conda environment

- Compose lifecycle controlled exclusively via CLI

- Platform bootstrap container successfully managed

---

**STATUS: COMPLETE**

**ACP now has a stable, extensible, professional-grade control interface.**

This CLI will become the primary interface through which all future ACP functionality is accessed.

From this point forward:

- users interact with ACP via the CLI

- infrastructure is internal implementation

- smoke tests, diagnostics, and job submission will integrate into the CLI

---


## MinIO data lake online (2026-03-02)

### Objective
Brought up MinIO as the S3-compatible object store for ACP and provisioned the canonical lakehouse bucket (`aether-lakehouse`) via an init-style `mc` container.

This establishes a stable, cloud-like storage substrate so all future systems (Spark, Iceberg, Trino, streaming sinks) can write to a consistent S3 API and a consistent lake layout.

### Design decisions
- MinIO chosen as the local equivalent of AWS S3 (zero-cost, Docker-friendly, widely supported).
- An `mc` init container was used to create the bucket deterministically at boot.
- Lake layout prefixes (`bronze/`, `silver/`, `gold/`) are created immediately to enforce conventions straight away.

### Fix applied
Initial boot failed due to an invalid pinned `minio/mc` image tag (Docker registry did not publish the specified tag).
Updated pins to published release tags:
- `minio/minio:RELEASE.2025-01-20T14-49-07Z`
- `minio/mc:RELEASE.2025-01-17T23-25-50Z`

### Verification
- `aether up` brings up MinIO and reports `healthy`.
- Bucket persisted on the MinIO data volume (`docker exec acp-minio ls /data` shows `aether-lakehouse`).
- MinIO Console reachable at `http://localhost:9001` and bucket visible.
- `mc ls` confirms objects/prefixes exist inside the bucket.

---

**STATUS: COMPLETE**

**MinIO S3 lakehouse storage verified**

MinIO lakehouse successfully established with `gold/silver/bronze` layered architecture with deterministic bucket initiation (Init container `apc-mc-init` exits with exit code 0 after bucket creation)

---

## Streaming (Redpanda) (2026-03-02)

### Objective
Added Redpanda as ACP’s Kafka-compatible event streaming backbone and Redpanda Console for UI inspection.

A one-shot init container (`rpk-init`) creates the baseline topic `aether.events` at boot, making topic existence part of the platform contract rather than a manual setup step.

### Why Redpanda
Redpanda provides the Kafka API without the heavier operational footprint of ZooKeeper-era Kafka setups. For ACP this keeps the local platform fast, reproducible, and realistic enough to map cleanly onto cloud Kafka offerings.

### Verification
- `rpk topic list` shows `aether.events` with 1 partition and 1 replica.
- Produced 10 messages (`event_1` … `event_10`) and observed offsets 0–9.
- Consumed the same 10 messages back reliably via `rpk topic consume`.

---

**STATUS: COMPLETE**

**Confirmed message consumption, proved Redpanda service functionality.**

---

## Spark cluster online

### Objective
Bring up a Spark cluster (master and worker) and prove it can run a real job that writes **Parquet** into the MinIO `aether-lakehouse` bucket.

Iceberg was not implemented at this stage. Focus is on: **compute → object storage → verify**.

---

## Review of what ACP is so far (MinIO + Redpanda + Spark)

ACP is a local cloud platform. It runs a small set of core services that future planned projects (ODIN, CHRONOS, etc.) will plug into.

So far, three essential building blocks are online:

### 1) MinIO (S3-style object storage)
**What it is:** MinIO is an object store that speaks the same API as AWS S3.  
**Why MinIO:** In modern data platforms, the data lake is predominantly object storage (S3). It’s cost effective, scalable, and fits both batch and streaming pipelines.

**How it works in ACP:**
- Run MinIO in Docker.
- Created a bucket called `aether-lakehouse`.
- Inside that bucket enforced a lake layout: `bronze/`, `silver/`, `gold/`.
- Spark writes files to paths like:

  `s3a://aether-lakehouse/bronze/acp/sample_events/dt=YYYY-MM-DD/*.parquet`

**Important note:** Object storage (S3) is not a normal filesystem, You write to it via the S3 API.

---

### 2) Redpanda (Kafka-compatible streaming)
**What it is:** Redpanda is a Kafka-compatible streaming broker.
**Why Redpanda:** Streaming is how platforms can handle high-volume event data (flight events, meter readings, logs). Instead of writing files directly, producers publish events to a topic; consumers read those events and process them.

**How it works in ACP:**
- Run Redpanda in Docker.
- Created a baseline topic: `aether.events`.
- Verified it by producing and consuming messages reliably.
- This forms the basis for later milestones where Spark Streaming will read from Kafka topics and write to Iceberg tables.

---

### 3) Spark (distributed compute)
**What it is:** Spark is a distributed compute engine for big data. It can run:
- batch jobs (read data, transform it, write results)
- streaming jobs (continuously process Kafka topics)

**Why Spark:** Spark is ACP's Elastic MapReduce equivalent compute layer.
It’s how:
- raw events in Kafka are ingested into bronze tables
- bronze into silver aggregates
- silver into gold metrics and rankings

**How it works in ACP:**
- Run a Spark **Standalone cluster** (master + worker).
- The master schedules work, the worker executes tasks.
- You can submit a job into the cluster with `spark-submit`.
- In ACP, this is wrapped behind the CLI so it’s a one-liner job execution.

---

## What was done

### Services online (Spark cluster)
- `spark-master`: Spark scheduler + UI
- `spark-worker-1`: executes Spark tasks

### Scripts / logic
- A small Spark job (`scripts/spark_write_parquet.py`) that:
  1) generates 100 synthetic rows
  2) prints `ROW_COUNT=100` (verification)
  3) writes Parquet to MinIO under a date partition (`dt=...`)
  4) prints `WROTE_PARQUET_TO=...` (verification)

### CLI improvements
Added CLI commands to avoid giant, fragile commands:

- `aether spark-run scripts/spark_write_parquet.py`
  - runs `spark-submit` inside the Spark master container
  - injects the required S3A configuration (endpoint + credentials)
  - hides the long `--packages` and `--conf` boilerplate

- `aether ls bronze/acp/sample_events`
  - lists objects in MinIO using `mc`
  - used for deterministic verification of the file successfully entering the bronze layer of the `aether-lakehouse` bucket in MinIO 

---

## Why these design choices
### Why Parquet first, not Iceberg?
Iceberg adds many extra moving parts (catalog + metadata + table semantics).
Before adding that complexity, I wanted to prove a simpler truth:
- **Spark can write to MinIO reliably.**

That makes later Iceberg failures easier to isolate in future implementation.

### Why inject S3 config at submit time?
I avoided baking credentials into images or hardcoding them into config files.
Instead, the CLI reads `.env` and injects:
- endpoint: `http://minio:9000` (inside Docker network)
- access key / secret key
- path-style access and SSL settings suitable for MinIO
This keeps the cluster configuration clean and portable.

### Why the CLI needed `.env` interpolation?
Docker Compose expands values like:
`AWS_ACCESS_KEY_ID=${MINIO_ROOT_USER}`

But the CLI is a separate program and must interpret `.env` too.
Without interpolation, the CLI might pass literal strings like `${MINIO_ROOT_USER}` as credentials, which leads to authentication failures.

---

## Problems hit and solutions

### 1) Spark write initially failed with 403 Forbidden
**Symptom:** Spark could run, but writing to S3A gave `403 Forbidden`.  
**Cause:** CLI `.env` loader did not expand `${VAR}` references. Credentials were wrong.  
**Fix:** Implement `${VAR}` interpolation in the CLI `.env` parsing, so Compose-style `.env` works everywhere.

### 2) `aether ls` initially didn’t list anything useful
**Symptom:** I saw “Added alias successfully” but no listing output.  
**Cause:** `mc alias set` was executed in one ephemeral container and the `mc ls` ran in another. Aliases aren’t shared across containers.  
**Fix:** Run alias setup and listing in the same `docker run ... /bin/sh -lc` invocation.

---

## Verification

### Commands
- `aether spark-run scripts/spark_write_parquet.py`
- `aether ls bronze/acp/sample_events`

### Expected output
- Spark prints:
  - `ROW_COUNT=100`
  - `WROTE_PARQUET_TO=s3a://aether-lakehouse/bronze/acp/sample_events/dt=YYYY-MM-DD/`
- MinIO listing shows:
  - `dt=YYYY-MM-DD/_SUCCESS`
  - `dt=YYYY-MM-DD/part-....snappy.parquet`

### Observed (2026-03-02)
- `ROW_COUNT=100`
- `WROTE_PARQUET_TO=s3a://aether-lakehouse/bronze/acp/sample_events/dt=2026-03-02/`
- `_SUCCESS` and Parquet part file visible via `aether ls` and in the MinIO console

---

**STATUS: COMPLETE**

**Successfully ran spark cluster and proved it can run a real job that writes **Parquet** into the MinIO `aether-lakehouse` bucket.**

---

## Querying aether-lakehouse with Trino (2026-03-03)

### Objective

Prove that data written by Spark into MinIO (object storage) can be queried via Trino.

This completes the first true lakehouse loop inside ACP:

- **Compute → Object Storage → SQL Query Engine**

Specifically:

- Spark writes Parquet to MinIO (`s3a://aether-lakehouse/...`)

- Trino registers that location as a table

- Trino queries the data successfully

- The row count matches what Spark wrote

This validates that ACP’s storage and query layers are properly wired.

---

### Background

To this point the following was verified:

- MinIO was running and healthy

- Spark could write Parquet files into the bucket

- Redpanda was operational

- The lakehouse directory structure (`bronze/, silver/, gold/`) existed

**However:**

- There was no SQL visibility into the stored data

- Parquet files existed physically, but not logically as tables

Object storage by itself is just a filesystem.
SQL engines do not automatically discover folders as tables.

To query data, a catalog must register:

- Table name

- Schema (columns and types)

- File format

- Location

---

### Important concept

The distinction between files and tables was paramount to this step.

Consider a folder like what I created previously:

- `s3a://aether-lakehouse/bronze/acp/sample_events/dt=2026-03-02/`

This contains Parquet files. However:

- **A file path is not a table**

- A SQL engine queries tables, it cannot discober folders as tables

Therefore, a catalog was used as a mapping mechanism to map the folder in MinIO  →  table in Trino.

---

### Initial Issues

Initially a singular lake catalog was attempted to be used for everything. This caused a multitude of faliures:

#### 1. `external_location` not recognised

When running: 

```sql
CREATE TABLE lake.bronze.sample_events_20260302 (...)
WITH (external_location=..., format='PARQUET');
```

The following was returned:

```bash
Catalog 'lake' table property 'external_location' does not exist
```

This was because the `lake` catalog was configured as **Iceberg** as I attempted to do this first despite previous devlog entries, so another approach was needed.

### Resolution

Instead of forcing a singular connector to handle two different, I separated responsibilities with distinct catalogs.

#### `raw` Catalog (Hive Connector)

Purpose:
- Query raw Parquet folders

- Register external tables

- Provide file-level SQL visibility

Configuration: 

```properties
connector.name=hive
hive.metastore.uri=thrift://hive-metastore:9083

# allow external/non-managed writes 
hive.non-managed-table-writes-enabled=true

# Trino native S3 filesystem (MinIO)
fs.native-s3.enabled=true
s3.endpoint=http://minio:9000
s3.region=eu-west-2
s3.path-style-access=true
s3.aws-access-key=${ENV:MINIO_ROOT_USER}
s3.aws-secret-key=${ENV:MINIO_ROOT_PASSWORD}
```

This catalog configuration allows:

- Native S3 access (MinIO compatible)
- External tables pointing as specific folders

---

#### `lake` Cataglog (Iceberg Connector)

Purpose:

- Future state for structured lakehouse tables

- Schema evolution

- Table metadata

- Snapshot support

I deliberately did not use Iceberg for raw Parquet querying because:

- Iceberg requires Spark to write Iceberg metadata.

- The Spark job currently operating writes plain Parquet.

Therefore, raw handles ingestion visibility.
lake will handle structured lakehouse tables later.

This separation reduced complexity and eliminated connector property conflicts.

**`lake` Catalog Configuration:**

```properties
connector.name=iceberg

# metastore
hive.metastore.uri=thrift://hive-metastore:9083

# native S3 (MinIO)
fs.native-s3.enabled=true
s3.endpoint=http://minio:9000
s3.region=eu-west-2
s3.path-style-access=true
s3.aws-access-key=${ENV:MINIO_ROOT_USER}
s3.aws-secret-key=${ENV:MINIO_ROOT_PASSWORD}
```
---

#### Issue 2: S3 and S3A distinction

I encountered errors such as:

- `No FileSystem for scheme "s3"`

- `InvalidAccessKeyId`

- `Configuration property not used`

These stem from mixing:

- `Hadoop S3A (s3a://)`

- `Trino native S3 (s3://)`

- `Legacy hive.s3.*`

- `Native s3.*`

**Solution:**

- Standardised on native S3 with proper endpoint config

- Used s3a:// only where Hive connector required it

- Removed unused properties (Trino fails fast on unknown config)

**Lesson:**
S3-compatible systems are strict about which filesystem implementation is active.
Using the wrong scheme triggers the wrong code path.

---

### Implementation

I implemented steps into the CLI for clean execution and avoiding fragile docker execution commands.

**Commands are as follows:**

#### Create `raw` Catalog

After restarting trino (`aether restart`)

```bash
aether sql "SHOW CATALOGS"
```

**Result:**
```bash
lake
raw
system
```

This confirmed the new `raw` catalog was loaded correctly.

---

#### Create and Register Schema in Bronze

```bash
aether bronze register sample_events_20260302 2026-03-02
```

This executes the following:

```sql
CREATE SCHEMA IF NOT EXISTS raw.bronze
WITH (location='s3a://aether-lakehouse/bronze/');
```
and:

```sql
CREATE TABLE raw.bronze.sample_events_20260302 (
  event_id bigint,
  dt varchar
)
WITH (
  external_location='s3a://aether-lakehouse/bronze/acp/sample_events/dt=2026-03-02/',
  format='PARQUET'
);

```

This does not copy data, it communicates with Trino describing the table name and its corresponding folder and schema.

---

#### Validation with SQL

**Show table:**
```bash
aether bronze tables
```

Output:

```bash
sample_events_20260302
```

**Inspect sample rows:**

```bash
aether bronze sample sample_events_20260302 --limit 5
```

Output:

```bash
0 | 2026-03-02
1 | 2026-03-02
2 | 2026-03-02
3 | 2026-03-02
4 | 2026-03-02
```

This Matched Spark's deterministic generation.

**Confirm schema:**

```bash
aether bronze describe sample_events_20260302
```

Output:

```bash
event_id  bigint
dt        varchar
```

**Confirm row count:**

```bash
aether bronze count sample_events_20260302
```

Output:

```bash
100
```

Matched Spark's printed `ROW_COUNT=100`.

---

### Architectural Insight

```text
Redpanda → Spark → MinIO (Parquet) → Trino (raw catalog)
                                  ↘ Iceberg (lake catalog, future)
```


Bronze layer:

- File-based ingestion

- Externally mapped tables

Future Silver/Gold:

- Iceberg-managed tables

- Structured lakehouse semantics
---

**STATUS: COMPLETE**

ACP now supports:

- Local object storage (MinIO)

- Distributed compute (Spark)

- SQL analytics engine (Trino)

- Metadata layer (Hive Metastore)

- External table registration

- Cross-component interoperability

**Most importantly:**

ACP is no longer purely infrastructure.
It is now queryable.

---


## Bronze to Silver Transformation Pipeline (2026-03-12)

### Objective
I wanted to implement a silver layer transformation pipeline within the Aether Cloud Platform lakehouse architecture.

Previously, I validated that raw bronze datasets stored in object storage can be queried via Trino. So naturally, I wanted to expand upon this by introducing data transformation and layered data modelling.

The silver layer represents cleaned and structured datasets derived from the raw Bronze layer data.

This development serves to demonstrate the ACP can support an authentic data engineering workflow such as the following: 

```txt
Bronze (raw data)
        ↓
Spark transformations
        ↓
Silver (structured datasets)
        ↓
SQL analytics via Trino
```

---


### Architecture Context

Aether Cloud Platform follows the canonical lakehouse structure: bronze, silver, and gold layers.

**Each layer serves a specific role:**

#### Bronze

The bronze layer is the raw ingestion layer.

**The bronze layer is characterised by the following:**

- Minimally transformed (raw data is preserved, nothing changed from ingestion)
- Schema flexible (No specific schema structure has been designed or enforced)
- Optimised for ingestion speed
- Usually not partitioned (unless necessary for very large data or streaming but even then this tends to be a very course partition (day/hour partitions))

#### Silver

The silver layer is the structued transformation layer.

**Silver layer characteristics:**

- Cleaned data 
- Normalised types
- Analytics-friendly schema
- partitioned storage
- Some engineered data fields (such as metadata fields such as ingestion timestamps for liniage purposes)

---

### Implementation Overview

The silver transformation pipeline consists of three components:

- Spark transformation job
- Silver data storage in MinIO
- Trino table registration and partition discovery 

---

### Spark Transformation

A Spark job was implemented to convert Bronze records into Silver format.

Spark job file: `scripts/bronze_to_silver.py`


**This job performs three operations:**

#### Read Bronze Data

The bronze Parquet files are read from MinIO: `s3a://aether-lakehouse/bronze/acp/sample_events/`

#### Transform Schema

The bronze schema:

```sql
event_id BIGINT
dt VARCHAR
```

Was transformed into:

```sql
event_id BIGINT
event_date DATE
ingest_ts TIMESTAMP
```

The transformations include:

- converting `dt` into a typed `DATE`
- adding an `ingest_ts` timestamp column
- enforcing a stable schema for downstream analytics

#### Write Silver Dataset

The transformed dataset is written to: `s3a://aether-lakehouse/silver/acp/sample_events/`

With partitioning enabled: `partitionBy("event_date")`

Therefore, the resulting storage layout is:

```txt
silver/acp/sample_events/
    event_date=2026-03-02/
        part-0000.parquet
```

**Note:** Partitioning improves query performance by allowing SQL query engines (Trino in this case) to prune irrelevant data during scans.

---

### Silver Dataset Registration

In order to query the silver data through Trino, the dataset must be registered as an external table in the Hive Metastore.

**Note:** The following SQL was executed using the ACP CLI `aether sql <SQL COMMAND>` format

**Schema creation:**

```sql
CREATE SCHEMA IF NOT EXISTS raw.silver
WITH (location='s3a://aether-lakehouse/silver/');
```

**Table registration:**

```sql
CREATE TABLE raw.silver.sample_events (
  event_id bigint,
  ingest_ts timestamp,
  event_date date
)
WITH (
  external_location='s3a://aether-lakehouse/silver/acp/sample_events/',
  format='PARQUET',
  partitioned_by = ARRAY['event_date']
)
```

---


### Partition Discovery

#### Issue Encountered

During validation of the silver transformation pipeline, initial queries returned empty counts:

```sql
SELECT count(*) FROM raw.silver.sample_events
```

returned 0 despite the fact that the Spark transformation reported: `SILVER_ROW_COUNT=100`, and the files were present in object storage.

#### Root cause

Spark successfully wrote partitioned silver Parquet files. However, the Hive Metastore had not yet discovered the partition folders.

Spark created this partitioned directory structure:

```txt
event_date=2026-03-02/
```

This was as expected. But, the metastore initially only registered the table itself, and not the partitions.

Consequently, Trine interpreted this as the table containing no partitions, resulting in the empty query result.

#### Resolution

Partition metadata was synchronised using the Trino system procedure:

```sql
CALL raw.system.sync_partition_metadata(
    'silver',
    'sample_events',
    'FULL'
)
```

This command searches the table's storage location and registers all partition folders within the metastore.

After synchronisation, the partition: `event_data=2026-03-02` was correctly registered.

#### Validation

After the partition synchronisation, the silver dataset queries returned the anticipated results.

**Row count validation:**

```sql
SELECT count(*) FROM raw.silver.sample_events
```

Returns `100`

**Partition validation:**

```sql

SELECT event_date, count(*)
FROM raw.silver.sample_events
GROUP BY event_date

```

Returns `2026-03-02       100`

**Schema validation:**

```sql
DESCRIBE raw.silver.sample_events
```

Returns:

```sql
event_id BIGINT
event_date DATE
ingest_ts TIMESTAMP
```

This verifies that the bronze to silver layer transformation pipeline is operating correctly.

---

### Some Takeaway Lessons

This part of the ACP development exposed a common lakehouse behavioural quirk:

- Object storage layout and SQL metadata must remain synchronised.

So, when using external partitioned tables:

- data files alone are not sufficient
- the metastore must be made aware of partition locations

Modern lakehouse formats such as Iceberg and Delta Lake handle metadata automatically.

However, right now ACP uses Hive external tables that require explicit partition discovery.

---

### Outcomes

I have successfully implemented the ACP Silver layer. Now, ACP supports bronze, silver data engineering workflows and the foundation of higher level analytics has been established.

**Note:** Also implemented silver command wiring into the CLI (silver registration and silver synchronisation, and some basic verification queries: count and sample)

---


**STATUS: COMPLETE**

ACP now supports:

- Bronze to silver synchronisation

- Silver data partitioning

- Metadata synchronisation

- Foundation for higher level analytics

**Most importantly:**

ACP now supports a real data engineering workflow

---

## Silver to Gold Analytics Layer (2026-03-12)

### Objective

I wanted to implement a Gold analytics layer within Aether Cloud Platform's lakehouse architecture.

The silver layer introduced structured datasets derived from the Bronze data, the Gold layer represents curated analytics outputs designed for direct consumption.

Gold datasets will typically contain:

- aggregated metrics
- dimensional summaries
- business-oriented views of the data

This part of the development serves to demonstrate the ACP can transform operational datsets into analytics-prepared outputs.

The gold datasets represents the final stage of data modelling before consumption by dashboards, reports and machine learning workflows. With the competion of the gold layer, ACP has a full data engineering workflow capability.

---

### Gold Dataset Design

For the initial Gold dataset, a simple analytical table was implemented:

```bash
daily_event_counts
```

With the following schema:

```sql
event_date DATE
event_count BIGINT
load_ts TIMESTAMP
```

This is a basic baseline gold table designed to answer the question: How many events occured per day?

This is a very simple table, but it demonstrates the full analytical workflow of ACP.

---

### Spark Aggregation Pipeline

I implemented a Spark job the aggregate the Silver dataset into the Gold dataset: `scripts/silver_to_gold.py`

**Input:**

Silver dataset stored in MinIO: `s3a://aether-lakehouse/silver/acp/sample_events/`

**Transformation:**

The Spark job performs a grouped aggregation:

```sql
GROUP BY event_date
COUNT(*)
```

A processing timestamp (`load_ts`) was added to record when the Gold dataset was generated.

**Output:**

The Gold dataset was written to: `s3a://aether-lakehouse/gold/acp/daily_event_counts/`

The resulting dataset contains one row per event date.

---

### Gold Registration in Trino

To enable SQL queries, the Gold dataset was registered as an external table in Trino.

Schema creation: 

```sql
CREATE SCHEMA IF NOT EXISTS raw.gold
WITH (location='s3a://aether-lakehouse/gold/');
```

Table definiation:
```sql
CREATE TABLE raw.gold.daily_event_counts (
  event_date date,
  event_count bigint,
  load_ts timestamp
)
WITH (
  external_location='s3a://aether-lakehouse/gold/acp/daily_event_counts/',
  format='PARQUET'
);
```

Since this gold dataset is not partitioned, no metadata synchronisation step was warranted.

---

### Validation

I used some verification queries to confirm the integrity of the ACP pipeline:

**Silver row count:**

```sql
SELECT count(*) FROM raw.silver.sample_events
```

Result: `100` 

**Gold aggregation check:**

```sql
SELECT sum(event_count) FROM raw.gold.daily_event_counts
```

Result: `100` 


This verifies that the aggregation preserved all the records from the silver dataset

---

### Outcome

ACP now supports a complete analytical workflow:

```txt
Spark ingestion
      ↓
Bronze dataset storage
      ↓
Spark transformation
      ↓
Silver structured dataset
      ↓
Spark aggregation
      ↓
Gold analytical dataset
      ↓
SQL analytics via Trino
```

---


**STATUS: COMPLETE**

ACP now supports:

- Silver to Gold layer aggregations

- Analytics ready Gold layer data


**Most importantly:**

ACP now a functioning end-to-end analytics platforms rather than a data storage system

---

## ACP Stress Test (ODIN flight dataset)

### Objective

From up to this stage in development, the Aether Cloud Platform pipeline has only been validated using a small synthetic dataset. This has served to be sufficient for the confirmation of the correctness of the bronze, silver, and cold architecture and transformations, but it did not demonstrate that ACP could handle realistic datasets with realistic characteristics such as:

- large row numbers
- missing values
- inconsistent delay metrics
- categorical aviation dimensions (carriers, routes)
- realistic distributions of operation data

To authentically validate ACP's robustness, I used a real aviation dataset as a more thorough test case (since a future project planned is ODIN, a avition based project)

The dataset was sourced from a flight operation dataset (BTS-style scheme) and stored locally as `odin_test_dataset.csv`.

This dataset contained 539,747 flight records with the following fields:

```txt
OP_UNIQUE_CARRIER
ORIGIN
DEST
DEP_DELAY_NEW
ARR_DELAY_NEW
CANCELLED
DISTANCE
```

The objective of this part of the ACP development was the truely confirm that ACP can successfully:

- Ingest a real dataset into the Bronze layer
- Clean and structure data in the Silver layer
- Produce aggregated analytics in the Gold layer
- Maintain data consistency across all these layers

---

### Bronze Layer: Raw Flight Data Ingestion

#### Ingestion Approach

The law CSV dataset was placed in a staging location at `data/staging/odin/flights`, and this data path was added to the docker compose volumes for the spark master and worker.

Then the raw CSV was ingested using a Spark job:

```bash
aether spark-run scripts/ingest_odin_bronze.py
```

This job performed the following operations:

- Read the CSV file with header detection and schema inference
- Normalized column names to snake_case
- Appended ingestion metadata columns
- Wrote the dataset to the ACP Bronze lakehouse

So, the ODIN bronze dataset was written to:

```txt
s3a://aether-lakehouse/bronze/odin/flights/
```

Additional provenance columns were also added: 

| Column        | Purpose                       |
| ------------- | ----------------------------- |
| `source_file` | identifies the dataset source |
| `ingest_ts`   | timestamp of ingestion        |


This serves to ensure bronze records have data lineage and remain traceable to the ingestion source.

#### Bronze Schema

```sql
op_unique_carrier
origin
dest
dep_delay_new
arr_delay_new
cancelled
distance
source_file
ingest_ts
```

#### Bronze Validation Queries

```sql
SELECT count(*) FROM raw.bronze.odin_flights
```

Result: `539747`

**Sample records:**

```txt
WN,PHX,BWI,82.0,57.0,0.0,1999.0
DL,ATL,LIT,9.0,1.0,0.0,453.0
AA,ABQ,DFW,NULL,NULL,1.0,569.0
```

**Observations:**

- missing delay values correctly appeared as `NULL`
- cancellation flag is preserves
- numeric values were inferred correctly

This authenticates that the bronze ingestion layer can process large real datasets without schema corruption.

---

### Silver Layer: Structure Flight Data

#### Transformation Objectives

The silver layer transforms the bronze data into cleaner and more prepared data suitable for analytics while simultaneously preserving the raw data characteristics of the bronze layer.

**Improvements applied:**

- column normalization
- explicit typing
- semantic naming

#### Silver Transformation Script

```bash
aether spark-run scripts/bronze_to_silver_odin.py
```

#### Transformations Applied

| Bronze Column     | Silver Column     |
| ----------------- | ----------------- |
| op_unique_carrier | carrier           |
| dep_delay_new     | dep_delay_minutes |
| arr_delay_new     | arr_delay_minutes |
| cancelled         | cancelled_flag    |
| distance          | distance_miles    |


This transformation preserved the null values and did not involve any artificial imputation.

**Silver Storage Location:**

```txt
s3a://aether-lakehouse/silver/odin/flights/
```

#### Silver Validation

**Row count verification:**

```sql
SELECT count(*) FROM raw.silver.odin_flights
```

Result: `539747`

This confirms that no records were lost during the transformation.

**Schema verification:**

```sql
DESCRIBE raw.silver.odin_flights
```

Result:

```bash
carrier varchar
origin varchar
dest varchar
dep_delay_minutes double
arr_delay_minutes double
cancelled_flag double
distance_miles double
source_file varchar
ingest_ts timestamp
```

So, the silver dataset is structure for analytics while maintaining the bronze lineage.

---

### Gold Layer: Carrier Analytics

#### Purpose

Produce the first really meaningful analytics table in ACP using real flight data.

Because the dataset does not contain a flight data column providing any temporal context, time-series aggregations were not possible. So, instead I attempted a carrier-level operation summary.

#### Gold Transformation Script

```bash
aether spark-run script/silver_to_gold_odin.py
```

#### Aggregations

| Metric                | Description             |
| --------------------- | ----------------------- |
| flight_count          | total flights           |
| avg_dep_delay_minutes | average departure delay |
| avg_arr_delay_minutes | average arrival delay   |
| cancelled_count       | total cancellations     |
| avg_distance_miles    | average flight distance |


#### Gold Storage

```txt
s3a://aether-lakehouse/gold/odin/carrier_delay_summary/
```

#### Gold Validation

**Carrier count:**

```sql
SELECT count(*) FROM raw.gold.carrier_delay_summary
```

Result: `14` the number of distinct carriers

**Top carriers by flight volume:**

```sql
SELECT * 
FROM raw.gold.carrier_delay_summary
ORDER BY flight_count DESC
LIMIT 10
```

Output:

```txt
WN 105307 flights
DL 76306 flights
AA 75088 flights
OO 65036 flights
UA 62007 flights
```

#### Cross-layer Integrity Check

To certify that the aggregations are correct:

```sql
SELECT sum(flight_count)
FROM raw.gold.carrier_delay_summary
```

Result: `539747`

This exactly matches the Bronze and Silver layer row counts. Thus, authenticating that the Gold aggregation pipeline also preserved all the records.

#### Note on Spark Builds

All the ACP architecture layers for the ODIN test data were built with a specific spark build configuration, only with variations to app_name for clarity when viewing the Spark job logs.

The general Spark build form is as follows:

```python
def build_spark(app_name: str) -> SparkSession: 
  return ( 
    SparkSession.builder .appName(app_name) 
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") 
    .config("spark.hadoop.fs.s3a.endpoint", os.environ["S3_ENDPOINT"]) 
    .config("spark.hadoop.fs.s3a.access.key", os.environ["AWS_ACCESS_KEY_ID"]) 
    .config("spark.hadoop.fs.s3a.secret.key", os.environ["AWS_SECRET_ACCESS_KEY"]) 
    .config("spark.hadoop.fs.s3a.path.style.access", "true") 
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") 
    .getOrCreate() )
```

This was implemented since the existing Spark configuration defined Iceberg catalog storage settings. These iceberg settings only apply when interacting with Iceberg tables via the `lake` catalog

However, the bronze ingestion job writes plain parquet files directly to an `s3a://` path, which uses Hadoop S3A filesystem layer, NOT the Iceberg catalog.

This resulted with a 403 forbidden error that was rectified using the spark build format used above. The Spark session builder configured the S3A access using environment variables already injected into the Spark containers.

---

### Engineering Observations

#### Null Handling

Real avidation datasets tend to contain missing values such as a missing delay. ACP preserved these nulls without introducing any bias.

#### Schema Robustness

Spark inference and Trino querying behaved consistently across the Bronze and Silver layers.

#### Lakehouse Integration

The pipeline successfully demonstrated interoperability between:

- Spark
- MinIO object storage
- Trino query engine

#### Data Scale

Processing approximately 540K rows confirmed that ACP can handle cases of non-trivial dataset volumnes.

---

### Outcomes

I have validated ACP against a realistic aviation dataset.

ACP successfully executed a full data lifecycle, transforming raw data in bronze to silver, and gold, resulting in actual real analytics all with the following properties:

- consistent row counts across layers
- clean schema transformations
- reliable object storage integration
- accurate analytical outputs



---


**STATUS: COMPLETE**

**ACP is now validated as a functional local lakehouse platform that is capable of handling realistic data pipelines**

---






