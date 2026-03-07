from __future__ import annotations

import os
from datetime import datetime, timezone

from pyspark.sql import SparkSession
from pyspark.sql.functions import lit, current_timestamp


def main() -> None:
    dt = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    bucket = os.environ.get("S3_BUCKET", "aether-lakehouse")

    spark = (
        SparkSession.builder
        .appName("acp-iceberg-smoke")
        .config(
            "spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
        )
        .config("spark.sql.catalog.lake", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.lake.type", "hive")
        .config("spark.sql.catalog.lake.uri", "thrift://hive-metastore:9083")
        .config("spark.sql.catalog.lake.warehouse", f"s3a://{bucket}/warehouse")
        .getOrCreate()
    )

    n = 100
    df = (
        spark.range(0, n)
        .withColumnRenamed("id", "event_id")
        .withColumn("ts", current_timestamp())
        .withColumn("value", lit(1.0))
        .withColumn("dt", lit(dt))
    )

    print(f"ROW_COUNT={df.count()}")
    df.writeTo("lake.bronze.sample_events").append()

    print("WROTE_ICEBERG_TABLE=lake.bronze.sample_events")
    spark.stop()


if __name__ == "__main__":
    main()