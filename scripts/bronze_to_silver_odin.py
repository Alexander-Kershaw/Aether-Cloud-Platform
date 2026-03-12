from __future__ import annotations

import os

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp, lit

"""
==============================================================================================================================

Testing ODIN test data bronze to silver transformation:

- Reads the bronze ODIN example data Parquet
- Rename columns to cleaner silver names
- Cast types explicitly
- Keeps nulls
- Writes silver parquet

==============================================================================================================================
"""


def main() -> None:
    spark = (
        SparkSession.builder
        .appName("acp-bronze-to-silver-odin") #ODIN specific naming
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.endpoint", os.environ["S3_ENDPOINT"])
        .config("spark.hadoop.fs.s3a.access.key", os.environ["AWS_ACCESS_KEY_ID"])
        .config("spark.hadoop.fs.s3a.secret.key", os.environ["AWS_SECRET_ACCESS_KEY"])
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .getOrCreate()
    )

    bronze_path = "s3a://aether-lakehouse/bronze/odin/flights/"
    silver_path = "s3a://aether-lakehouse/silver/odin/flights/"

    bronze_df = spark.read.parquet(bronze_path)

    silver_df = (
        bronze_df
        .select(
            col("op_unique_carrier").cast("string").alias("carrier"),
            col("origin").cast("string").alias("origin"),
            col("dest").cast("string").alias("dest"),
            col("dep_delay_new").cast("double").alias("dep_delay_minutes"),
            col("arr_delay_new").cast("double").alias("arr_delay_minutes"),
            col("cancelled").cast("double").alias("cancelled_flag"),
            col("distance").cast("double").alias("distance_miles"),
            col("source_file").cast("string").alias("source_file"),
            col("ingest_ts").alias("ingest_ts"),
        )
    )

    row_count = silver_df.count()
    print(f"=====| SILVER_ODIN_ROW_COUNT={row_count} |=====")

    (
        silver_df
        .write
        .mode("overwrite")
        .parquet(silver_path)
    )

    print(f"=====| WROTE_SILVER_ODIN_TO={silver_path} |=====")

    spark.stop()


if __name__ == "__main__":
    main()