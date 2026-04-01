select
    snapshot_date,
    item_name,
    sell_listings_count,
    sell_price_cents,
    sell_price_usd,
    sale_price_usd_from_text
from {{ ref('stg_items') }}
