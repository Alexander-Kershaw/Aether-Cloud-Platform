***
## ACP Layer Execution Templates
***

### Bronze Template

#### Purpose

Bronze ingestion land raw or lightly normalized source data into a project-scoped lakehouse storage.

#### Standard Storage Pattern

```txt
bronze/<project>/<dataset>/
```

**Example:**

```txt
bronze/odin/flights/
bronze/chronos/demand/
bronze/acp/sample_events/
```

#### Standard Table Naming

```txt
raw.bronze.<project>_<dataset>
```

**Examples:**

```txt
raw.bronze.odin_flights
raw.bronze.chronos_demand
raw.bronze.acp_sample_events
```

#### Standard Spark Bronze Template

```python
from __future__ import annotations

import os
import sys

from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp, lit


def main() -> None:
    project = os.environ["ACP_PROJECT"]
    dataset = os.environ["ACP_DATASET"]
    source_path = os.environ["ACP_SOURCE_PATH"]
    bronze_path = f"s3a://aether-lakehouse/bronze/{project}/{dataset}/"

    spark = (
        SparkSession.builder
        .appName(f"acp-ingest-{project}-bronze-{dataset}")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.endpoint", os.environ["S3_ENDPOINT"])
        .config("spark.hadoop.fs.s3a.access.key", os.environ["AWS_ACCESS_KEY_ID"])
        .config("spark.hadoop.fs.s3a.secret.key", os.environ["AWS_SECRET_ACCESS_KEY"])
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .getOrCreate()
    )

    df = (
        spark.read
        .option("header", True)
        .option("inferSchema", True)
        .csv(source_path)
    )

    bronze_df = (
        df
        .withColumn("source_file", lit(source_path))
        .withColumn("ingest_ts", current_timestamp())
    )

    row_count = bronze_df.count()
    print(f"=====| BRONZE_ROW_COUNT={row_count} |=====")

    (
        bronze_df
        .write
        .mode("overwrite")
        .parquet(bronze_path)
    )

    print(f"=====| WROTE_BRONZE_TO={bronze_path} |=====")

    spark.stop()


if __name__ == "__main__":
    main()

```

---

### Silver Template

#### Purpose

Silver transforms the Bronze data into cleaned, typed, and normalized datasets with more suitable naming and explict type casting.

#### Standard Storage Pattern

```txt
silver/<project>/<dataset>/
```

#### Standard Table Naming

```txt
raw.silver.<project>_<dataset>
```

#### Standard Spark Silver Template

```python
from __future__ import annotations

import os

from pyspark.sql import SparkSession


def main() -> None:
    project = os.environ["ACP_PROJECT"]
    dataset = os.environ["ACP_DATASET"]

    bronze_path = f"s3a://aether-lakehouse/bronze/{project}/{dataset}/"
    silver_path = f"s3a://aether-lakehouse/silver/{project}/{dataset}/"

    spark = (
        SparkSession.builder
        .appName(f"acp-bronze-to-silver-{project}-{dataset}")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.endpoint", os.environ["S3_ENDPOINT"])
        .config("spark.hadoop.fs.s3a.access.key", os.environ["AWS_ACCESS_KEY_ID"])
        .config("spark.hadoop.fs.s3a.secret.key", os.environ["AWS_SECRET_ACCESS_KEY"])
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .getOrCreate()
    )

    bronze_df = spark.read.parquet(bronze_path)

    # Project-specific transformation logic goes here
    silver_df = bronze_df

    row_count = silver_df.count()
    print(f"=====| SILVER_ROW_COUNT={row_count} |=====")

    (
        silver_df
        .write
        .mode("overwrite")
        .parquet(silver_path)
    )

    print(f"=====| WROTE_SILVER_TO={silver_path} |=====")

    spark.stop()


if __name__ == "__main__":
    main()

```

---

### Gold Template

#### Purpose

Gold produces the curated business facing marts and aggregates.

#### Standard Storage Pattern

```txt
gold/<project>/<model>/
```

#### Standard Table Naming

```txt
raw.gold.<project>_<model>
```

#### Standart Spark Gold Template

```python
from __future__ import annotations

import os

from pyspark.sql import SparkSession
from pyspark.sql.functions import avg, col, count, current_timestamp, sum as spark_sum


def main() -> None:
    project = os.environ["ACP_PROJECT"]
    dataset = os.environ["ACP_DATASET"]

    silver_path = f"s3a://aether-lakehouse/silver/{project}/{dataset}/"
    gold_path = f"s3a://aether-lakehouse/gold/{project}/{model}/"

    spark = (
        SparkSession.builder
        .appName(f"acp-silver-to-gold-{project}-{model}")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.endpoint", os.environ["S3_ENDPOINT"])
        .config("spark.hadoop.fs.s3a.access.key", os.environ["AWS_ACCESS_KEY_ID"])
        .config("spark.hadoop.fs.s3a.secret.key", os.environ["AWS_SECRET_ACCESS_KEY"])
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .getOrCreate()
    )

    silver_path = f"s3a://aether-lakehouse/silver/{project}/{dataset}/"
    gold_path = f"s3a://aether-lakehouse/gold/{project}/{model}/"

    silver_df = spark.read.parquet(silver_path)


    # Perform project specific gold aggregations and transformations here
    gold_df = silver_df

        
    row_count = gold_df.count()
    print(f"=====| GOLD_ROW_COUNT={row_count} |=====")

    (
        gold_df
        .write
        .mode("overwrite")
        .parquet(gold_path)
    )

    print(f"=====| WROTE_GOLD_TO={gold_path} |=====")

    spark.stop()


if __name__ == "__main__":
    main()

```



#### Standard SQL Gold Template

```SQL
-- Ensure schema exists
CREATE SCHEMA IF NOT EXISTS raw.gold;

-- Remove prior table metadata
DROP TABLE IF EXISTS raw.gold.<project>_<model>;

-- Create table with explicit location
CREATE TABLE raw.gold.<project>_<model> (
    <column_1> <type_1>,
    <column_2> <type_2>,
    built_at TIMESTAMP(3)
)
WITH (
    external_location = 's3a://aether-lakehouse/gold/<project>/<model>/',
    format = 'PARQUET'
);

-- Populate table
INSERT INTO raw.gold.<project>_<model>
SELECT
    ...
FROM raw.silver.<project>_<dataset>;
```

---
