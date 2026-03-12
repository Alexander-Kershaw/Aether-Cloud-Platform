from __future__ import annotations

import os

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp, lit

"""
==============================================================================================================================

Testing bronze ingestion to ACP lakehouse:

- Reads test CSV
- Keep source columns mostly intact
- Converts names to snake_case
- Adds metadata source_files and ingest_ts
- Write to Parquet

==============================================================================================================================
"""


def main() -> None:
    spark = (
        SparkSession.builder
        .appName("acp-ingest-odin-bronze")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.endpoint", os.environ["S3_ENDPOINT"])
        .config("spark.hadoop.fs.s3a.access.key", os.environ["AWS_ACCESS_KEY_ID"])
        .config("spark.hadoop.fs.s3a.secret.key", os.environ["AWS_SECRET_ACCESS_KEY"])
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .getOrCreate()
    )

    source_path = "/opt/aether/data/staging/odin/flights/odin_test_dataset.csv"
    bronze_path = "s3a://aether-lakehouse/bronze/odin/flights/"

    df = (
        spark.read
        .option("header", True)
        .option("inferSchema", True)
        .csv(source_path)
    )

    bronze_df = (
        df
        .select(
            col("OP_UNIQUE_CARRIER").alias("op_unique_carrier"),
            col("ORIGIN").alias("origin"),
            col("DEST").alias("dest"),
            col("DEP_DELAY_NEW").alias("dep_delay_new"),
            col("ARR_DELAY_NEW").alias("arr_delay_new"),
            col("CANCELLED").alias("cancelled"),
            col("DISTANCE").alias("distance"),
        )
        .withColumn("source_file", lit("odin_test_dataset.csv"))
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