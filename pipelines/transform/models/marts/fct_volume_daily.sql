select
    price_date as date,
    item_name,
    total_sales_volume as sales_volume,
    avg_price_usd,
    min_price_usd,
    max_price_usd
from {{ ref('int_item_price_history_daily') }}