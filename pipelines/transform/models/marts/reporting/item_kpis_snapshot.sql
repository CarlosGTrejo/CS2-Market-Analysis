select
    v.date,
    v.item_name,
    -- 7d average sales volume (liquidity index)
    avg(v.sales_volume) over (
        partition by v.item_name
        order by UNIX_DATE(v.date)
        range between 6 preceding and current row
    ) as liquidity_index_7d_avg,
    -- 30d average sales volume (liquidity index)
    avg(v.sales_volume) over (
        partition by v.item_name
        order by UNIX_DATE(v.date)
        range between 29 preceding and current row
    ) as liquidity_index_30d_avg,
    -- 7d sum sales volume
    sum(v.sales_volume) over (
        partition by v.item_name
        order by UNIX_DATE(v.date)
        range between 6 preceding and current row
    ) as sales_volume_7d_sum,
    -- 30d sum sales volume
    sum(v.sales_volume) over (
        partition by v.item_name
        order by UNIX_DATE(v.date)
        range between 29 preceding and current row
    ) as sales_volume_30d_sum,
    -- Active sell price (from market snapshot)
    m.sell_price_usd
from {{ ref('fct_volume_daily') }} v
left join {{ ref('fct_market_snapshot_daily') }} m
    on v.item_name = m.item_name and v.date = m.snapshot_date
qualify v.date = (select max(date) from {{ ref('fct_volume_daily') }})