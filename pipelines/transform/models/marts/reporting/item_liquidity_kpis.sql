select
    date,
    item_name,
    
    avg(sales_volume) over (
        partition by item_name
        order by date
        range between interval 6 day preceding and current row
    ) as liquidity_index_7d,

    avg(sales_volume) over (
        partition by item_name
        order by date
        range between interval 29 day preceding and current row
    ) as liquidity_index_30d

from {{ ref('fct_volume_daily') }}