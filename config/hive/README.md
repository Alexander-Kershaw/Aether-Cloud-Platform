# Hive Metastore Auxiliary JARs

These JARs extend the Hive Metastore container with drivers required by ACP.

The official Hive Docker image does not include:

• S3 filesystem support  
• AWS SDK dependencies  
• PostgreSQL JDBC driver

ACP requires all three.

---

## Files

### hadoop-aws-3.3.4.jar
Provides Hadoop S3A filesystem support.

Required for Hive/Trino to access MinIO using:

s3a://aether-lakehouse/...

---

### aws-java-sdk-bundle-1.12.262.jar
AWS SDK dependency used by the Hadoop S3A connector.

Even though ACP uses MinIO locally, it implements the S3 API,
so the AWS SDK is still required.

---

### postgresql.jar
PostgreSQL JDBC driver used by Hive Metastore.

Allows the metastore service to connect to:

jdbc:postgresql://metastore-db:5432/metastore

---

## Why these are committed

They are version-pinned and mounted into the Hive container via Docker:

/opt/hive/auxlib/

Committing them ensures:

• reproducible builds
• no runtime downloads
• deterministic dependency versions