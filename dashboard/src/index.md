---
theme: [midnight, alt, wide]
toc: false
sql:
  rpt_commodity_velocity_daily: data/rpt_commodity_velocity_daily.parquet
  rpt_item_metrics_latest: data/rpt_item_metrics_latest.parquet
  rpt_market_metrics_daily: data/rpt_market_metrics_daily.parquet
---

# Market Overview

```sql id=commodity_metrics
SELECT
  is_commodity,
  market_date,
  total_estimated_trade_volume_usd::DOUBLE AS total_estimated_trade_volume_usd,
  total_active_supply,
  total_units_sold,
  group_turnover_rate * 100 AS group_turnover_rate,
  avg_bid_ask_spread_pct::DOUBLE * 100 AS avg_bid_ask_spread_pct
FROM rpt_commodity_velocity_daily
ORDER BY market_date
LIMIT 2;
```

```sql id=[current_market_metrics]
SELECT 
  market_date,
  total_estimated_trade_volume_usd::DOUBLE AS total_estimated_trade_volume_usd,
  total_active_supply,
  total_units_sold,
  market_turnover_rate * 100 AS market_turnover_rate,
  avg_bid_ask_spread_pct::DOUBLE * 100 AS avg_bid_ask_spread_pct
FROM rpt_market_metrics_daily
ORDER BY market_date DESC
LIMIT 1
```

```js
const market_date = new Date(current_market_metrics?.market_date);
```

<div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));">

  <div class="card">
    <h2>Total Estimated Trade Volume</h2>
    <span class="big" style="color: var(--theme-foreground-focus);">$${Number(current_market_metrics?.total_estimated_trade_volume_usd || 0).toFixed(2)}</span>
    <h3><i>* Calculated using median sales data</i></h3>
  </div>

  <div class="card">
    <h2>Market Turnover Rate</h2>
    <span class="big">${(current_market_metrics?.market_turnover_rate || 0).toFixed(1)}%</span>
    <h3>Calculated as: Total Units Sold / Active Supply</h3>
  </div>

  <div class="card">
    <h2>Total Market Supply</h2>
    <span class="big">${(current_market_metrics?.total_active_supply || "0").toLocaleString()}</span>
    <h3>Active Listings</h3>
  </div>

  <div class="card">
    <h2>Total Units Sold</h2>
    <span class="big">${(current_market_metrics?.total_units_sold || "0").toLocaleString()}</span>
    <h3>Over the past day</h3>
  </div>

  <div class="card">
    <h2>Market Spread</h2>
    <span class="big">${Number(current_market_metrics?.avg_bid_ask_spread_pct || 0).toFixed(1)}%</span>
    <h3>Average Bid-Ask Gap</h3>
  </div>
</div>



```js
Plot.plot({
  title: "Daily Liquidity Matrix",
  subtitle: `Market State as of ${market_date.toLocaleDateString()}`,
  grid: true,
  color: {
    legend: true,
    scheme: "category10"
  },
  x: { nice: true, label: "Group Turnover Rate (%)" },
  y: { nice: true, label: "Avg Bid-Ask Spread (%)" },
  marks: [
    Plot.dot(commodity_metrics, {
      x: "group_turnover_rate",
      y: "avg_bid_ask_spread_pct",
      fill: (d) => d.is_commodity ? "Commodities" : "Non-Commodities",
      r: {
        value: "total_estimated_trade_volume_usd",
        label: "EST. Trade Vol. (USD)",
      },
      channels: {
        active_supply: {
          label: "Active Supply",
          value: "total_active_supply"
        },
        units_sold: {
          label: "Units Sold",
          value: "total_units_sold"
        }
      },
      tip: {
        format: {
          fill: false,
          units_sold: true,
          active_supply: true,
        }
      }
    })
  ]
})
```