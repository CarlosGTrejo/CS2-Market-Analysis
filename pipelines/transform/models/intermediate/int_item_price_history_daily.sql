select
    item_name,
    date(price_timestamp) as price_date,
    sum(sales_volume) as total_sales_volume,
    avg(price_usd) as avg_price_usd,
    min(price_usd) as min_price_usd,
    max(price_usd) as max_price_usd
from {{ ref('stg_item_price_history') }}
group by 1, 2
