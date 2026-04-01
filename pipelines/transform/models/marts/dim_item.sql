select
    item_name,
    class_id,
    market_bucket_group_id,
    market_bucket_group_name,
    item_type,
    name_color,
    is_tradable,
    is_commodity
from {{ ref('int_items_latest') }}