select
    date,
    item_name,
    -- 7d volume
    sum(sales_volume) over (
        partition by item_name
        order by UNIX_DATE(date)
        range between 6 preceding and current row
    ) as volume_7d,

    -- 30d volume
    sum(sales_volume) over (
        partition by item_name
        order by UNIX_DATE(date)
        range between 29 preceding and current row
    ) as volume_30d

from {{ ref('fct_volume_daily') }}