#!/usr/bin/env bash
set -e

mkdir -p config/hive/lib
cd config/hive/lib

echo "=====|Downloading Hive auxiliary jars...|====="

curl -L -o hadoop-aws-3.3.4.jar \
https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar

curl -L -o aws-java-sdk-bundle-1.12.262.jar \
https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar

curl -L -o postgresql.jar \
https://jdbc.postgresql.org/download/postgresql-42.7.3.jar

echo "Hive dependencies downloaded."