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