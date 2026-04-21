{{ config(
    cluster_by=["item_name", "item_type", "bucket_group_name"]
) }}

with fct_market_daily as (

    select * from {{ ref('fct_market_daily') }}
    where market_date >= '2000-01-01'

),

latest_dates as (

    select 
        item_name, 
        max(market_date) as max_market_date
    from fct_market_daily
    group by 1

),

latest_item_metrics as (

    select
        fct_market_daily.item_name,
        fct_market_daily.item_type,
        fct_market_daily.bucket_group_name,
        fct_market_daily.is_commodity,

        fct_market_daily.ask_count,
        fct_market_daily.ask_price_usd,
        fct_market_daily.bid_price_usd,
        fct_market_daily.units_sold,
        fct_market_daily.total_estimated_trade_volume_usd,
        fct_market_daily.bid_ask_spread_pct,
        fct_market_daily.turnover_rate,
        fct_market_daily.bid_ask_ratio,

        fct_market_daily.market_date

    from fct_market_daily
    inner join latest_dates
        on fct_market_daily.item_name = latest_dates.item_name
        and fct_market_daily.market_date = latest_dates.max_market_date

)

select * from latest_item_metrics