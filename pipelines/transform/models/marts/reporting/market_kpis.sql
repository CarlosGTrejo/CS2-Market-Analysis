select
    snapshot_date,
    -- Total Market Volume
    sum(sell_listings_count) as total_market_volume,

    -- Average Listing Premium: Average percentage difference between listing price and actual sale price, indicating how much sellers are asking above the final sale price on average.
    avg((sell_price_usd - sale_price_usd_from_text) / nullif(sale_price_usd_from_text, 0) * 100) as avg_listing_premium

from {{ ref('fct_market_snapshot_daily') }}
group by snapshot_date