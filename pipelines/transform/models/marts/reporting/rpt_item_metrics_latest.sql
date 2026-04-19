{{ config(
    cluster_by=["item_name", "item_type", "bucket_group_name"]
) }}

with

fct_market_daily as (

    select * from {{ ref('fct_market_daily') }}
    -- Satisfies BigQuery's partition filter while ensuring we catch 
    -- the last traded date for highly illiquid items.
    where market_date >= '2000-01-01'

),

dim_item as (

    select * from {{ ref('dim_item') }}

),

latest_item_metrics as (

    select
        ---------- ids / strings
        fct_market_daily.item_name,
        dim_item.item_type,
        dim_item.bucket_group_name,

        ---------- numerics
        fct_market_daily.ask_count,
        fct_market_daily.ask_price_usd,
        fct_market_daily.bid_price_usd,
        fct_market_daily.units_sold,
        fct_market_daily.total_estimated_trade_volume_usd,
        fct_market_daily.bid_ask_spread_pct,
        fct_market_daily.turnover_rate,
        fct_market_daily.quick_sell_ratio,

        ---------- booleans
        dim_item.is_commodity,

        ---------- dates
        fct_market_daily.market_date

    from fct_market_daily

    inner join dim_item
        on fct_market_daily.item_name = dim_item.item_name
        
    qualify row_number() over (
        partition by fct_market_daily.item_name 
        order by fct_market_daily.market_date desc
    ) = 1

)

select * from latest_item_metrics