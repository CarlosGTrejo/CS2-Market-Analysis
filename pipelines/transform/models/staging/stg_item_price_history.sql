WITH source AS (
    SELECT * FROM {{ source('raw_market_data', 'item_price_history_external') }}
),

renamed_and_casted AS (
    SELECT
        -- Identifiers
        CAST(market_hash_name AS STRING) AS item_name,
        
        -- Dates/Times
        -- The Steam market API often returns dates like "Jul 16 2013 01: +0". 
        PARSE_TIMESTAMP('%b %d %Y %H: +0', date) AS price_timestamp,
        
        -- Metrics
        CAST(price AS NUMERIC) AS price_usd,
        CAST(volume AS INT64) AS sales_volume,
        
        -- dlt pipeline metadata (optional, but good for lineage/auditing)
        CAST(_dlt_id AS STRING) AS dlt_id,
        CAST(_dlt_load_id AS STRING) AS dlt_load_id
    FROM source
),

deduplicated AS (
    SELECT *
    FROM renamed_and_casted
    -- BigQuery best-practice deduplication: Keep the most recently loaded record per item & timestamp
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY item_name, price_timestamp
        ORDER BY dlt_load_id DESC
    ) = 1
)

SELECT *
FROM deduplicated