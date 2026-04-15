select
    price_date as date,
    item_name,
    total_sales_volume as sales_volume,
    min_median_sale_price_usd,
    max_median_sale_price_usd
from {{ ref('int_item_price_history_daily') }}

{% if is_incremental() %}
    where price_date > (select max(date) from {{ this }})
{% endif %}