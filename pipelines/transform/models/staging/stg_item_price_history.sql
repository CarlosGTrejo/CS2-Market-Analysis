-- TODO: consider adding a surrogate key?

with item_price_history_raw as (
    select * from {{ source('raw_market_data', 'item_price_history_raw') }}
),

renamed_and_casted as (
    select
        ---------- ids
        -- dlt pipeline metadata (optional, but good for lineage/auditing)
        cast(_dlt_id as string) as _dlt_id,
        cast(_dlt_load_id as string) as _dlt_load_id,

        ---------- strings
        cast(market_hash_name as string) as item_name,
        
        ---------- numerics
        cast(price as numeric) as median_sale_price_usd,
        cast(volume as int64) as units_sold,
        
        ---------- timestamps
        cast(date as timestamp) as priced_at

    from item_price_history_raw
),

deduplicated as (
    select *
    from renamed_and_casted
    -- BigQuery best-practice deduplication: Keep the most recently loaded record per item & timestamp
    qualify row_number() over (
        partition by item_name, priced_at
        order by _dlt_load_id desc
    ) = 1
)

select *
from deduplicated