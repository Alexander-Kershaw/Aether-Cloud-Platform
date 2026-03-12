***
# AETHER Cloud Platform CLI Manual
***

The ACP CLI (`aether`) serves as a unified inferface for managing and performing operation on the data platform.

It wraps Docker Compose, Spark jobs, MinIO access, Redpanda utilities, and Trino SQL execution for ease of execution.

The CLI is implemented using **Typer** and is intalled via:

```bash
pip install -e .
```

Once installed, commands are run using this general form:

```bash
aether <command>
```

---

## Core Stack Commands

### Start ACP

```bash
aether up
```

Starts the full Aether Cloud Platform stack using Docker Compose.

**The services launched include:**

- MinIO (object storage)
- Redpanda (streaming platform)
- Spark master and worker
- Hive Metastore
- Postgres (metastore database)
- Trino (SQL query engine)

---

### Stop ACP

```bash
aether down
```

Stops and removes all the running ACP containers.

---

### Restart ACP

```bash
aether restart
```

This is equivalent to:

```bash
aether down
aether up
```

---

### Stack Status

```bash
aether status
```

This displays:

- Compose configuration checks
- Docker container status

---

### System Diagnostics

```bash
aether doctor
```

Run diagnostic checks:

- Docker installation
- `.env` configuration
- Required networks ports

This command assists in the identification of local environment issues.

---

### Spark Job Execution

#### Run Spark Script

```bash
aether spark-run scripts/my_job.py
```

This submits a Spark job to the cluster.

Internally this executes:

```bash
spark-submit --master spark://spark-master:7077
```

This requires packages for:

- Hadoop S3A filesystem
- AWS SDK
- Iceberg runtime

Spark jobs are ran inside the `spark-master` container.

---

### Object Storage Commands

#### List Objects in MinIO

```bash
aether ls bronze/acp/sample_events
```

Lists objects in the MiniIO bucket.

This uses the `mc` client inside a temporary container.

Example output:

```bash
bronze/acp/sample_events/dt=2026-03-02/part-00000.parquet
```

---

### SQL Query Execution

#### Execute SQL

```bash
aether sql "SELECT count (*) FROM raw.bronze.sample_events_20260302"
```

This executes the SQL query through the Trino CLI inside the Trino container.

This allows the direct querying of the data lake.

---

## Bronze Layer Commands

The bronze commands manage external Parquet tables registered in Trino.

This tables map raw storage locations to SQL tables.

---

### Register Bronze Table 

```bash
aether bronze register sample_events_20260302 2026-03-02
```

Registers a Parquet partition as s SQL tabel.

Equivalent SQL;

```SQL
CREATE TABLE raw.bronze.sample_events_20260302
WITH (
 external_location='s3a://aether-lakehouse/bronze/acp/sample_events/dt=2026-03-02/',
 format='PARQUET'
)
```

---

### List Bronze Tables

```bash
aether bronze tables
```

Displays tables in the Bronze schema.


---

### Bronze Row Count

```bash
aether bronze count sample_events_20260302
```

Validates row counts for the dataset.

---

### Sampple Bronze Data

```bash
aether bronze sample sample_events_20260302
```

Shows the first few rows of the dataset.

---

### Describe Bronze Table

```bash
aehter bronze describe sample_events_20260302
```

Displays the table schema.

---

## Redpanda Commands

### List Topics

```bash
aether redpanda topics
```

---

### Produce Test Message

```bash
aether redpanda produce aether.events
```

---

### Consume Messages

```bash
aether redpanda consume aether.events
```

---

## Example Workflow

**Start platform**

```bash
aether up
```

**Run Spark ingestion**

```bash
aether spark-run scriopts/spark_write_iceberg.py
```

**Register bronze table**

```bash
aether bronze register sample_events_20260302 2036-03-02
```

**Query data**

```bash
aether sql "SELECT count(*) FROM raw.bronze.sample_events_20260302"
```

**inspect records**

```bash
aether bronze sample sample_events_20260302
```

---