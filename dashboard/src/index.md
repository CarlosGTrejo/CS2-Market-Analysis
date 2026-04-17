---
theme: [midnight, alt, wide]
title: CS2 Market Analysis
toc: false
sql:
  market_kpis: data/market_kpis.parquet
  item_kpis_snapshot: data/item_kpis_snapshot.parquet
---

# CS2 Market Analysis

```sql id=[latest_market_kpis]
SELECT 
  snapshot_date,
  total_market_listings,
  CAST(avg_listing_premium AS DOUBLE) AS avg_listing_premium
FROM market_kpis 
ORDER BY snapshot_date DESC 
LIMIT 1
```

```sql id=[highest_volume_item]
SELECT * FROM item_kpis_snapshot
ORDER BY sales_volume_30d_sum DESC
LIMIT 1
```

```sql id=[highest_volume_item_7d]
SELECT * FROM item_kpis_snapshot
ORDER BY sales_volume_7d_sum DESC
LIMIT 1
```

```sql id=liquidity_items
SELECT
  item_name,
  CAST(sell_price_usd AS DOUBLE) AS sell_price_usd,
  daily_sales_7d_avg,
  daily_sales_30d_avg,
  sales_volume_7d_sum,
  sales_volume_30d_sum
FROM item_kpis_snapshot
ORDER BY daily_sales_30d_avg DESC
```

```sql id=top_10_momentum
SELECT 
  item_name,
  daily_sales_7d_avg,
  daily_sales_30d_avg
FROM item_kpis_snapshot
ORDER BY daily_sales_7d_avg DESC
LIMIT 10
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

<div class="grid grid-cols-3">
  <div style="display: flex; flex-direction: column; gap: 1rem;">
  <div class="card" style="flex: 1; margin: 0;">
    <h2>Average Listing Premium</h2>
    <span class="big" style="color: var(--theme-foreground-focus);">${Number(latest_market_kpis?.avg_listing_premium || 0).toFixed(2)}%</span>
    <h3>Average listing markup over historical sale price</h3>
  </div>
    
  <div class="card" style="flex: 1; margin: 0;">
    <h2>Total Market Listings</h2>
    <span class="big">${latest_market_kpis?.total_market_listings?.toLocaleString() || "0"}</span>
    <h3>Active Listings</h3>
  </div>
  </div>

  <div class="card grid-colspan-2" style="margin: 0;">
    <h2>Top 10 High-Momentum Items</h2>
    <h3>Comparing current 7-day daily sales against the 30-day historical average.</h3>

  ${dumbbellPlot}
    
  </div>
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
const searchItems = view(Inputs.search(liquidity_items));
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
