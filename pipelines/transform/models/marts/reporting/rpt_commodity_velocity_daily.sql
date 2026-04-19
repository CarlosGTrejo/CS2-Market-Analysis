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
        sum(fct_market_daily.daily_trade_volume_usd) as total_trade_volume_usd,
        sum(fct_market_daily.ask_count) as total_active_supply,
        sum(fct_market_daily.daily_units_sold) as total_units_sold,

        -- Group Turnover Rate
        case
            when sum(fct_market_daily.ask_count) > 0
                then sum(fct_market_daily.daily_units_sold) / sum(fct_market_daily.ask_count)
            else null
        end as group_turnover_rate,

        avg(fct_market_daily.bid_ask_spread_pct) as avg_bid_ask_spread_pct

    from fct_market_daily

    inner join dim_item
        on fct_market_daily.item_name = dim_item.item_name
        
    group by 1, 2

)

select * from joined_and_aggregated