select
    date,
    item_name,
    
    avg(sales_volume) over (
        partition by item_name
        order by UNIX_DATE(date)
        range between 6 preceding and current row
    ) as liquidity_index_7d,

    avg(sales_volume) over (
        partition by item_name
        order by UNIX_DATE(date)
        range between 29 preceding and current row
    ) as liquidity_index_30d

from {{ ref('fct_volume_daily') }}