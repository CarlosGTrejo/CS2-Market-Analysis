---
theme: dashboard
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
  total_market_volume,
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
  liquidity_index_7d_avg,
  liquidity_index_30d_avg,
  sales_volume_7d_sum,
  sales_volume_30d_sum
FROM item_kpis_snapshot
ORDER BY liquidity_index_30d_avg DESC
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
      y: "liquidity_index_30d_avg",
      fill: "item_name", // <-- THE FIX: Map fill to a specific data column
      r: 6,
      // Enables interactive tooltips on hover
      tip: true,
      // Customizes the tooltip text to show the item name alongside the coordinates
      title: (d) => `${d.item_name}\nPrice: $${d.sell_price_usd}\nSales: ${d.liquidity_index_30d_avg}`
    })
  ]
});
```

<div class="grid grid-cols-4 grid-rows-1">
  <div class="card">
    <h2>Average Listing Premium</h2>
    <span class="big" style="color: var(--theme-foreground-focus);">${Number(latest_market_kpis?.avg_listing_premium || 0).toFixed(2)}%</span>
    <h3>Average listing markup over historical sale price</h3>
  </div>

  <div class="card">
    <h2>Total Market Volume</h2>
    <span class="big">${latest_market_kpis?.total_market_volume?.toLocaleString() || "0"}</span>
    <h3>Active Listings</h3 >
  </div>

  <div class="card">
    <h2>Highest Volume Item Group (7d)</h2>
    <span class="big">${highest_volume_item_7d?.item_name || "N/A"}</span>
    <h3>${highest_volume_item_7d?.sales_volume_7d_sum?.toLocaleString() || "0"} transactions</h3>
  </div>

  <div class="card">
    <h2>Highest Volume Item Group (30d)</h2>
    <span class="big">${highest_volume_item?.item_name || "N/A"}</span>
    <h3>${highest_volume_item?.sales_volume_30d_sum?.toLocaleString() || "0"} transactions</h3>
  </div>
</div>

<div class="grid grid-cols-3 grid-rows-1 gap-4">
  <div class="card">
    <h2>Item Liquidity Analysis</h2>
    <h3>Use the search box and table below to explore how item price correlates with liquidity (average daily sales) across different items.</h3>

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
      "liquidity_index_7d_avg",
      "liquidity_index_30d_avg",
      "sales_volume_7d_sum",
      "sales_volume_30d_sum"
    ],
    header: {
      item_name: "Item Name",
      sell_price_usd: "Sell Price (USD)",
      liquidity_index_7d_avg: "Daily Sales (7d avg)",
      liquidity_index_30d_avg: "Daily Sales (30d avg)",
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
