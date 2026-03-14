DROP TABLE IF EXISTS raw.gold.odin_carrier_delay_summary;

CREATE TABLE raw.gold.odin_carrier_delay_summary (
    carrier varchar,
    flight_count bigint,
    avg_arr_delay double,
    avg_dep_delay double,
    std_arr_delay double,
    std_dep_delay double,
    built_at timestamp(3)
)
WITH (
    external_location = 's3a://aether-lakehouse/gold/odin/carrier_delay_summary/',
    format = 'PARQUET'
);

INSERT INTO raw.gold.odin_carrier_delay_summary
SELECT
    carrier,
    COUNT(*) AS flight_count,
    AVG(arr_delay_minutes) AS avg_arr_delay,
    AVG(dep_delay_minutes) AS avg_dep_delay,
    STDDEV(arr_delay_minutes) AS std_arr_delay,
    STDDEV(dep_delay_minutes) AS std_dep_delay,
    CAST(CURRENT_TIMESTAMP AS TIMESTAMP) AS built_at
FROM raw.silver.odin_flights
GROUP BY carrier;