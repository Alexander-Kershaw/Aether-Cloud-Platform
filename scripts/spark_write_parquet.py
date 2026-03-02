from __future__ import annotations

import os
from datetime import datetime, timezone

from pyspark.sql import SparkSession
from pyspark.sql.functions import lit


def main() -> None:
    spark = (
        SparkSession.builder
        .appName("acp-parquet-smoke")
        .getOrCreate()
    )

    # Small deterministic test dataset
    n = 100
    df = spark.range(0, n).withColumnRenamed("id", "event_id")
    dt = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    df = df.withColumn("dt", lit(dt))

    count = df.count()
    print(f"ROW_COUNT={count}")

    bucket = os.environ.get("S3_BUCKET", "aether-lakehouse")
    out = f"s3a://{bucket}/bronze/acp/sample_events/dt={dt}/"

    (
        df.coalesce(1)    
        .write.mode("overwrite")
        .parquet(out)
    )

    print(f"WROTE_PARQUET_TO={out}")
    spark.stop()


if __name__ == "__main__":
    main()