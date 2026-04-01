WITH source AS (
    SELECT * FROM {{ source('raw_market_data', 'items_external') }}
),

renamed_and_casted AS (
    SELECT
        -- Identifiers
        CAST(asset_description__market_hash_name AS STRING) AS item_name,
        SAFE_CAST(asset_description__classid AS INT64) AS class_id,
        CAST(asset_description__market_bucket_group_id AS STRING) AS market_bucket_group_id,
        
        -- Characteristics
        CAST(asset_description__type AS STRING) AS item_type,
        CAST(asset_description__name_color AS STRING) AS name_color,
        CAST(asset_description__market_bucket_group_name AS STRING) AS market_bucket_group_name,
        
        -- Booleans
        CAST(asset_description__tradable AS BOOL) AS is_tradable,
        CAST(asset_description__commodity AS BOOL) AS is_commodity,
        
        -- Pricing & Metrics
        SAFE_CAST(sell_listings AS INT64) AS sell_listings_count,
        SAFE_CAST(sell_price AS INT64) AS sell_price_cents,
        SAFE_CAST(sell_price AS NUMERIC) / 100 AS sell_price_usd,
        -- Extract numbers/decimals from text and cast safely:
        SAFE_CAST(REGEXP_REPLACE(sale_price_text, r'[^0-9\.]', '') AS NUMERIC) AS sale_price_usd_from_text,
        
        -- Dates
        SAFE_CAST(snapshot_date AS DATE) AS snapshot_date,
        
        -- dlt pipeline metadata
        CAST(_dlt_id AS STRING) AS dlt_id,
        CAST(_dlt_load_id AS STRING) AS dlt_load_id

    FROM source
),

deduplicated AS (
    SELECT *
    FROM renamed_and_casted
    -- BigQuery best-practice deduplication: Keep the most recent/populated record per item per date
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY item_name, snapshot_date 
        ORDER BY dlt_load_id DESC, sell_listings_count DESC
    ) = 1
)

SELECT *
FROM deduplicated