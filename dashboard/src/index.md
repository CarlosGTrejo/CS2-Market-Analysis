---
theme: [midnight, alt, wide]
title: CS2 Market Analysis
toc: false
sql:
  rpt_commodity_velocity_daily: data/rpt_commodity_velocity_daily.parquet
  rpt_item_metrics_latest: data/rpt_item_metrics_latest.parquet
  rpt_market_metrics_daily: data/rpt_market_metrics_daily.parquet
---

# CS2 Market Analysis

```sql id=commodity_velocity
SELECT
  is_commodity,
  market_date,
  total_estimated_trade_volume_usd::DOUBLE AS total_estimated_trade_volume_usd,
  total_active_supply,
  total_units_sold,
  group_turnover_rate AS group_turnover_rate,
  avg_bid_ask_spread_pct::DOUBLE * 100 AS avg_bid_ask_spread_pct
FROM rpt_commodity_velocity_daily
```

```sql id=item_metrics
SELECT
  item_name,
  item_type,
  bucket_group_name,
  ask_count,
  ask_price_usd::DOUBLE AS ask_price_usd,
  bid_price_usd::DOUBLE AS bid_price_usd,
  units_sold,
  total_estimated_trade_volume_usd::DOUBLE AS total_estimated_trade_volume_usd,
  bid_ask_spread_pct::DOUBLE * 100 AS bid_ask_spread_pct,
  turnover_rate,
  quick_sell_ratio::DOUBLE AS quick_sell_ratio,
  is_commodity,
  market_date
FROM rpt_item_metrics_latest
```

```sql id=[market_metrics]
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
// A non-reactive Map to safely hold selections across re-renders
const selectionMap = new Map();
```

```js
const selectedItems = (() => {
  // 1. Get the unique IDs currently checked in the visible table
  const checkedNames = new Set(itemsTable.map(d => d.item_name));

  // 2. Diff only the currently filtered rows against the table's state
  for (const item of searchItems) {
    if (checkedNames.has(item.item_name)) {
      selectionMap.set(item.item_name, item); // Add newly checked items
    } else if (selectionMap.has(item.item_name)) {
      // MICRO-OPTIMIZATION: Only invoke delete if the item is actually in the Map!
      selectionMap.delete(item.item_name);    
    }
  }

  // 3. Return the reactive array
  return Array.from(selectionMap.values());
})();
```

<!-- vvvvv TODO: FIX or use different plot vvvvv -->
```js
const itemsPlot = Plot.plot({
  color: {
    legend: true, // Tells Plot to render the legend
    scheme: "observable10"
  },
  grid: true,
  x: {
    label: "Sell Price (USD) →",
    type: "linear"
  },
  y: {
    label: "↑ Daily Sales (30d avg)",
    type: "linear"
  },
  marks: [
    // Base axes
    Plot.ruleX([0]),
    Plot.ruleY([0]),
    
    // Plot the reactive itemsTable variable
    Plot.dot(selectedItems, {
      x: "sell_price_usd",
      y: "daily_sales_30d_avg",
      fill: "item_name", // <-- THE FIX: Map fill to a specific data column
      r: 6,
      // Enables interactive tooltips on hover
      tip: true,
      // Customizes the tooltip text to show the item name alongside the coordinates
      title: (d) => `${d.item_name}\nPrice: $${d.sell_price_usd}\nSales: ${d.daily_sales_30d_avg}`
    })
  ]
});
```

<!-- vvvvv TODO: FIX or use different plot vvvvv -->
```js
// 1. Reshape the wide Arrow Table into a long-format array
// This gives Observable Plot the exact data structure it expects for groupY
const longData = [];
for (const d of top_10_momentum) {
  longData.push({
    item_name: d.item_name,
    period: "30-Day Avg",
    sales: Number(d.daily_sales_30d_avg)
  });
  longData.push({
    item_name: d.item_name,
    period: "7-Day Avg",
    sales: Number(d.daily_sales_7d_avg)
  });
}

// 2. Define the base mapping (equivalent to the 'xy' variable in the docs)
const xy = { x: "sales", y: "item_name" };

// 3. Build the plot mirroring the documentation's marks structure
const dumbbellPlot = Plot.plot({
  marginLeft: 200, // Space for item names
  height: 320,
  grid: true,
  x: {
    label: "Daily Sales (Average) →"
  },
  y: {
    label: null,
    // Sort items so the highest 7-day sales are at the top
  },
  color: {
    domain: ["7-Day Avg", "30-Day Avg"],
    range: ["#efb118", "#4269d0"], // Orange & Blue
    legend: true
  },
  marks: [
    // Uses groupY to find the min and max x-values for each item and draws a line between them
    Plot.ruleY(longData, Plot.groupY({ x1: "min", x2: "max" }, xy)),
    
    // Plots the dots, using the period column for the fill color
    Plot.dot(longData, {
      ...xy, 
      fill: "period", 
      r: 6,
      tip: true,
      title: (d) => `${d.item_name}\n${d.period}: ${d.sales.toFixed(2)}`
    })
  ]
});
```

<div class="grid grid-cols-5">
  <div class="card">
    <h2>Total _Estimated_ Trade Volume</h2>
    <span class="big" style="color: var(--theme-foreground-focus);">$${Number(market_metrics?.total_estimated_trade_volume_usd || 0).toFixed(2)}</span>
    <h3>_Calculated using median sales data_</h3>
  </div>
    
  <div class="card">
    <h2>Total Market Supply</h2>
    <span class="big">${market_metrics?.total_active_supply || "0"}</span>
    <h3>Active Listings</h3>
  </div>

  <div class="card">
    <h2>Total Units Sold</h2>
    <span class="big">${market_metrics?.total_units_sold || "0"}</span>
    <h3>Over the past day</h3>
  </div>
  <div class="card">
    <h2>Market Turnover Rate</h2>
    <span class="big">${(market_metrics?.market_turnover_rate || 0).toFixed(1)}%</span>
    <h3>Calculated as: Total Units Sold / Active Supply</h3>
  </div>
  <div class="card">
    <h2>Market Spread</h2>
    <span class="big">${Number(market_metrics?.average_bid_ask_spread_pct || 0).toFixed(1)}%</span>
    <h3>Average Bid-Ask Gap</h3>
  </div>
</div>

  <div class="card grid-colspan-2" style="margin: 0;">
    <h2>Top 10 High-Momentum Items</h2>
    <h3>Comparing current 7-day daily sales against the 30-day historical average.</h3>

  ${dumbbellPlot}
    
  </div>

<div class="grid grid-cols-3 grid-rows-1 gap-4">
  <div class="card">
    <h2>Item Liquidity Analysis</h2>
    <h3>Use the table to explore how item price correlates with liquidity (average daily sales) across different items.</h3>

  ${itemsPlot}

  </div>

  <div class="card grid-colspan-2" style="padding: 0px">
    <div style="padding: 1em 1em 0">

```js
const searchItems = view(Inputs.search(item_metrics));
```

  </div>

```js
const itemsTable = view(Inputs.table(searchItems, {
    value: searchItems.filter(d => selectionMap.has(d.item_name)),
    required: false,
    columns: [
      "item_name",
      "sell_price_usd",
      "daily_sales_7d_avg",
      "daily_sales_30d_avg",
      "sales_volume_7d_sum",
      "sales_volume_30d_sum"
    ],
    header: {
      item_name: "Item Name",
      sell_price_usd: "Sell Price (USD)",
      daily_sales_7d_avg: "Daily Sales (7d avg)",
      daily_sales_30d_avg: "Daily Sales (30d avg)",
      sales_volume_7d_sum: "Sales Volume (7d sum)",
      sales_volume_30d_sum: "Sales Volume (30d sum)"
    },
    format: {
      sell_price_usd: (d) => d == null ? "N/A" : `$${Number(d).toFixed(2)}`
    }
  }));
```

  </div>
</div>
