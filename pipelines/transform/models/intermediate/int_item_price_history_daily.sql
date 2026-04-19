with stg_item_price_history as (
    select * from {{ ref('stg_item_price_history') }}
),

daily_metrics as (
    select
        item_name,
        date(priced_at) as price_date,
        sum(units_sold) as units_sold,
        sum(units_sold * median_sale_price_usd) as total_estimated_trade_volume_usd,
        avg(median_sale_price_usd) as avg_median_sale_price_usd
        
    from stg_item_price_history
    group by 1, 2
)

select *
from daily_metrics