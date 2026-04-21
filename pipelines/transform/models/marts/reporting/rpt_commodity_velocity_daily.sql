{{ config(
    materialized='incremental',
    incremental_strategy='insert_overwrite',
    partition_by={
      "field": "market_date",
      "data_type": "date",
      "granularity": "day"
    },
    cluster_by=["is_commodity"]
) }}

with

fct_market_daily as (

    select * from {{ ref('fct_market_daily') }}

    {% if is_incremental() %}
        where market_date >= (select coalesce(max(market_date), '1970-01-01') from {{ this }})
    {% else %}
        where market_date >= '2000-01-01'
    {% endif %}

),

dim_item as (

    select * from {{ ref('dim_item') }}

),

joined_and_aggregated as (

    select
        ---------- strings / booleans
        dim_item.is_commodity,

        ---------- dates
        fct_market_daily.market_date,

        ---------- numerics
        sum(fct_market_daily.total_estimated_trade_volume_usd) as total_estimated_trade_volume_usd,
        sum(fct_market_daily.ask_count) as total_active_supply,
        sum(fct_market_daily.units_sold) as total_units_sold,

        -- Group Turnover Rate
        safe_divide(sum(fct_market_daily.units_sold), sum(fct_market_daily.ask_count)) as group_turnover_rate,

        avg(fct_market_daily.bid_ask_spread_pct) as avg_bid_ask_spread_pct

    from fct_market_daily

    inner join dim_item
        on fct_market_daily.item_name = dim_item.item_name
        
    group by 1, 2

)

select * from joined_and_aggregated