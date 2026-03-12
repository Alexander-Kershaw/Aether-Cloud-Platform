from __future__ import annotations

import os

from pyspark.sql import SparkSession
from pyspark.sql.functions import avg, col, count, current_timestamp, sum as spark_sum

"""
==============================================================================================================================

Testing ODIN silver to gold aggregations.

Gold dataframe designed to answer the following:

- How many flights per carrier?
- Which carriers have the higher average delays?
- How many cancellations per carrier?
- What is the typical flight distance by carrier?

==============================================================================================================================
"""


def main() -> None:
    spark = (
        SparkSession.builder
        .appName("acp-silver-to-gold-odin")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.endpoint", os.environ["S3_ENDPOINT"])
        .config("spark.hadoop.fs.s3a.access.key", os.environ["AWS_ACCESS_KEY_ID"])
        .config("spark.hadoop.fs.s3a.secret.key", os.environ["AWS_SECRET_ACCESS_KEY"])
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .getOrCreate()
    )

    silver_path = "s3a://aether-lakehouse/silver/odin/flights/"
    gold_path = "s3a://aether-lakehouse/gold/odin/carrier_delay_summary/"

    silver_df = spark.read.parquet(silver_path)

    gold_df = (
        silver_df
        .groupBy(col("carrier"))
        .agg(
            count("*").alias("flight_count"),
            avg(col("dep_delay_minutes")).alias("avg_dep_delay_minutes"),
            avg(col("arr_delay_minutes")).alias("avg_arr_delay_minutes"),
            spark_sum(col("cancelled_flag")).alias("cancelled_count"),
            avg(col("distance_miles")).alias("avg_distance_miles"),
        )
        .withColumn("load_ts", current_timestamp())
        .select(
            "carrier",
            "flight_count",
            "avg_dep_delay_minutes",
            "avg_arr_delay_minutes",
            "cancelled_count",
            "avg_distance_miles",
            "load_ts",
        )
    )

    row_count = gold_df.count()
    print(f"=====| GOLD_ODIN_ROW_COUNT={row_count} |=====")

    (
        gold_df
        .write
        .mode("overwrite")
        .parquet(gold_path)
    )

    print(f"=====| WROTE_GOLD_ODIN_TO={gold_path} |=====")

    spark.stop()


if __name__ == "__main__":
    main()