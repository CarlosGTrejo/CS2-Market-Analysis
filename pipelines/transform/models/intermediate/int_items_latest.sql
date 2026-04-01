with ranked_items as (
    select
        *,
        row_number() over (partition by item_name order by snapshot_date desc) as rn
    from {{ ref('stg_items') }}
)

select
    item_name,
    class_id,
    market_bucket_group_id,
    market_bucket_group_name,
    item_type,
    name_color,
    is_tradable,
    is_commodity
from ranked_items
where rn = 1
