{{ config(
    materialized='incremental',
    incremental_strategy='insert_overwrite',
    partition_by={
      "field": "market_date",
      "data_type": "date",
      "granularity": "day"
    },
    cluster_by=['item_name'],
    require_partition_filter=(target.name == 'prod') 
) }}

with

stg_items as (
    select * from {{ ref('stg_items') }}
    {% if is_incremental() %}
        -- Only process the days that are being run
        where snapshot_date >= (select coalesce(max(market_date), '1970-01-01') from {{ this }})
    {% endif %}
),

int_item_price_history_daily as (
    select * from {{ ref('int_item_price_history_daily') }}
),

joined as (
    select
        stg_items.item_name,
        stg_items.ask_count,
        stg_items.ask_price_usd,
        stg_items.bid_price_usd,

        coalesce(int_item_price_history_daily.units_sold, 0) as units_sold,
        coalesce(int_item_price_history_daily.total_estimated_trade_volume_usd, 0) as total_estimated_trade_volume_usd,
        int_item_price_history_daily.avg_median_sale_price_usd,

        safe_divide(stg_items.ask_price_usd - stg_items.bid_price_usd, stg_items.bid_price_usd) as bid_ask_spread_pct,

        safe_divide(coalesce(int_item_price_history_daily.units_sold, 0), stg_items.ask_count) as turnover_rate,

        safe_divide(stg_items.bid_price_usd, stg_items.ask_price_usd) as bid_ask_ratio,

        stg_items.snapshot_date as market_date

    from stg_items
    left join int_item_price_history_daily
        on stg_items.item_name = int_item_price_history_daily.item_name
        and stg_items.snapshot_date = int_item_price_history_daily.price_date
)

select * from joined