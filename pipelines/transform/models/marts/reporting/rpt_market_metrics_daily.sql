{{ config(
    materialized='incremental',
    incremental_strategy='insert_overwrite',
    partition_by={
      "field": "market_date",
      "data_type": "date",
      "granularity": "month"
    }
) }}

with

fct_market_daily as (

    select * from {{ ref('fct_market_daily') }}
    
    {% if is_incremental() %}
        -- Only scan the dates we need to update
        where market_date >= (select coalesce(max(market_date), '1970-01-01') from {{ this }})
          and market_date >= '1970-01-01'
    {% else %}
        -- Satisfies BigQuery's require_partition_filter constraint for full refreshes
        where market_date >= '2000-01-01'
    {% endif %}

),

aggregated_market_metrics as (

    select
        ---------- dates
        fct_market_daily.market_date,

        ---------- numerics
        sum(fct_market_daily.total_estimated_trade_volume_usd) as total_estimated_trade_volume_usd,
        sum(fct_market_daily.ask_count) as total_active_supply,
        sum(fct_market_daily.units_sold) as total_units_sold,

        -- Market Turnover Rate (Total Volume / Total Supply)
        safe_divide(sum(fct_market_daily.units_sold), sum(fct_market_daily.ask_count)) as market_turnover_rate,

        -- Market-wide Average Spread
        avg(fct_market_daily.bid_ask_spread_pct) as avg_bid_ask_spread_pct

    from fct_market_daily
    
    group by 1

)

select * from aggregated_market_metrics