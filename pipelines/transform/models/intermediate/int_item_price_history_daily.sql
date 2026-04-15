select
    item_name,
    date(price_timestamp) as price_date,
    sum(sales_volume) as total_sales_volume,
    min(median_sale_price_usd) as min_median_sale_price_usd,
    max(median_sale_price_usd) as max_median_sale_price_usd
from {{ ref('stg_item_price_history') }}
group by 1, 2
