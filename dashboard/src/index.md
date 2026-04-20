---
theme: [midnight, alt, wide]
toc: false
sql:
  rpt_commodity_velocity_daily: data/rpt_commodity_velocity_daily.parquet
  rpt_item_metrics_latest: data/rpt_item_metrics_latest.parquet
  rpt_market_metrics_daily: data/rpt_market_metrics_daily.parquet
---

# Market Overview

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

```sql id=commodity_metrics
SELECT
  is_commodity,
  market_date,
  total_estimated_trade_volume_usd::DOUBLE AS total_estimated_trade_volume_usd,
  total_active_supply,
  total_units_sold,
  group_turnover_rate,
  avg_bid_ask_spread_pct::DOUBLE AS avg_bid_ask_spread_pct
FROM rpt_commodity_velocity_daily
WHERE market_date = ${market_date}
```

```sql id=commodity_breakdown
SELECT 
  CASE WHEN is_commodity THEN 'Commodities' ELSE 'Non-Commodities' END AS category,
  total_active_supply AS value,
  'Total Active Supply' AS metric_type
FROM rpt_commodity_velocity_daily
WHERE market_date = ${market_date}

UNION ALL

SELECT 
  CASE WHEN is_commodity THEN 'Commodities' ELSE 'Non-Commodities' END AS category,
  total_units_sold AS value,
  'Total Units Sold' AS metric_type
FROM rpt_commodity_velocity_daily
WHERE market_date = ${market_date}

UNION ALL

SELECT 
  CASE WHEN is_commodity THEN 'Commodities' ELSE 'Non-Commodities' END AS category,
  total_estimated_trade_volume_usd::DOUBLE AS value,
  'Trade Volume (USD)' AS metric_type
FROM rpt_commodity_velocity_daily
WHERE market_date = ${market_date}
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

<div class="grid grid-cols-2">
  <div class="card">

  ```js
  Plot.plot({
    title: "Market Liquidity Profile",
    subtitle: `${market_date.toLocaleDateString()}`,
    grid: true,
    color: {
      legend: true,
      scheme: "observable10"
    },
    x: { nice: true, label: "Trading Turnover (%)", percent: true },
    y: { nice: true, label: "Relative Spread (%)", percent: true },
    marks: [
      Plot.dot(commodity_metrics, {
        x: "group_turnover_rate",
        y: "avg_bid_ask_spread_pct",
        r: {
          value: "total_estimated_trade_volume_usd",
          label: "EST. Trade Vol. (USD)",
        },
        fill: (d) => d.is_commodity ? "Commodities" : "Non-Commodities",
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

  </div>

  <div class="card">

  ```js
  Plot.plot({
    title: "Commodity Composition by Market Metrics",
    subtitle: `${market_date.toLocaleDateString()}`,
    y: { 
      grid: true, 
      percent: true, // Formats the Y-axis labels as percentages (0-100%)
      label: "% of Total" 
    },
    x: { 
      label: "", 
      domain: ["Total Active Supply", "Total Units Sold", "Trade Volume (USD)"] 
    },
    color: {
      scheme: "observable10",
      legend: true
    },
    marks: [
      Plot.barY(commodity_breakdown, {
        x: "metric_type",
        y: "value",
        fill: "category",
        offset: "normalize",
        channels: {
          actual_value: {
            label: "Value",
            value: "value"
          }
        },
        tip: {
          format: {
            x: false,
            y: false,
            actual_value: true,
            fill: true
          }
        }
      }),
      Plot.ruleY([0])
    ]
  })
  ```
  </div>
</div>