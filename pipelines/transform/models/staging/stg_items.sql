with source as (
    select * from {{ source('raw_market_data', 'items_external') }}
),

renamed_and_casted as (
    select
        -- Identifiers
        cast(asset_description__market_hash_name as string) as item_name,
        safe_cast(asset_description__classid as int64) as class_id,
        cast(asset_description__market_bucket_group_id as string) as market_bucket_group_id,
        
        -- Characteristics
        cast(asset_description__type as string) as item_type,
        cast(asset_description__name_color as string) as name_color,
        cast(asset_description__market_bucket_group_name as string) as market_bucket_group_name,
        
        -- Booleans
        cast(asset_description__tradable as BOOL) as is_tradable,
        cast(asset_description__commodity as BOOL) as is_commodity,
        
        -- Pricing & Metrics
        safe_cast(sell_listings as int64) as sell_listings_count,
        safe_cast(sell_price as int64) as sell_price_cents,
        safe_cast(sell_price as numeric) / 100 as sell_price_usd,
        -- Extract numbers/decimals from text and cast safely:
        safe_cast(regexp_replace(sale_price_text, r'[^0-9\.]', '') as numeric) as sale_price_usd_from_text,
        
        -- Dates
        safe_cast(snapshot_date as date) as snapshot_date,
        
        -- dlt pipeline metadata
        cast(_dlt_id as string) as dlt_id,
        cast(_dlt_load_id as string) as dlt_load_id

    from source
),

deduplicated as (
    select *
    from renamed_and_casted
    -- BigQuery best-practice deduplication: Keep the most recent/populated record per item per date
    qualify row_number() over (
        partition by item_name, snapshot_date 
        order by dlt_load_id desc, sell_listings_count desc
    ) = 1
)

select *
from deduplicated