{{ config(
    materialized='incremental',
    incremental_strategy='insert_overwrite',
    partition_by={
      "field": "market_date",
      "data_type": "date",
      "granularity": "day"
    },
    cluster_by=['item_name'],
    require_partition_filter=true
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

        coalesce(int_item_price_history_daily.daily_units_sold, 0) as daily_units_sold,
        coalesce(int_item_price_history_daily.daily_trade_volume_usd, 0) as daily_trade_volume_usd,
        int_item_price_history_daily.daily_avg_median_sale_price_usd,

        case
            when stg_items.bid_price_usd > 0
                then (stg_items.ask_price_usd - stg_items.bid_price_usd) / stg_items.bid_price_usd
            else null
        end as bid_ask_spread_pct,

        case
            when stg_items.ask_count > 0
                then coalesce(int_item_price_history_daily.daily_units_sold, 0) / stg_items.ask_count
            else null
        end as turnover_rate,

        case
            when stg_items.ask_price_usd > 0
                then stg_items.bid_price_usd / stg_items.ask_price_usd
            else null
        end as quick_sell_ratio,

        stg_items.snapshot_date as market_date

    from stg_items
    left join int_item_price_history_daily
        on stg_items.item_name = int_item_price_history_daily.item_name
        and stg_items.snapshot_date = int_item_price_history_daily.price_date
)

select * from joined