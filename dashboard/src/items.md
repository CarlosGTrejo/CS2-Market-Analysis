---
theme: [midnight, alt, wide]
toc: false
sql:
  rpt_item_metrics_latest: data/rpt_item_metrics_latest.parquet
---

# Item Explorer

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
  bid_ask_spread_pct::DOUBLE AS bid_ask_spread_pct,
  turnover_rate,
  bid_ask_ratio::DOUBLE AS bid_ask_ratio,
  is_commodity,
  market_date
FROM rpt_item_metrics_latest
```

```sql id=breakdown_by_bucket
WITH aggregated_data AS (
  SELECT
    bucket_group_name AS category,
    SUM(total_estimated_trade_volume_usd) AS trade_volume_usd,
    SUM(units_sold) AS units_sold,
    AVG(bid_ask_spread_pct) AS avg_bid_ask_spread_pct,
    AVG(turnover_rate) AS avg_turnover_rate
  FROM rpt_item_metrics_latest
  GROUP BY bucket_group_name
)
UNPIVOT aggregated_data
ON 
  trade_volume_usd AS 'Trade Volume (USD)',
  units_sold AS 'Total Units Sold',
  avg_bid_ask_spread_pct AS 'Avg Bid Ask Spread',
  avg_turnover_rate AS 'Avg Turnover Rate'
INTO
  NAME metric_type
  VALUE value
```

## USE A TEXT PLOT TO SHOW A MESSAGE INSTEAD OF THE BLANK CHART

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


<div class="grid grid-cols-2">
  <div class="card">

  ```js
  const hasSelection = selectedItems.length > 0;
  const X_LABEL = "Turnover Rate";
  const Y_LABEL = "Bid-Ask Spread %";

  const scatter_plot = Plot.plot({
    title: "Turnover vs Bid-Ask Spread",
    grid: true,
    color: {
      legend: true,
      scheme: "observable10"
    },
    x: { nice: true, percent: true, label: hasSelection ? X_LABEL : null },
    y: { nice: true, percent: true, label: hasSelection ? Y_LABEL : null },
    marks: [
      ...(hasSelection ? [] : [Plot.text(["Click items in the table below to explore their metrics"], {
        frameAnchor: "middle", 
        fontSize: 18,
        fill: "#999",  // Light gray for less prominence
        fontStyle: "italic"
      })]),
      ...(hasSelection ? [Plot.ruleX([0]), Plot.ruleY([0])] : []),
      Plot.dot(selectedItems, {
        x: "turnover_rate",
        y: "bid_ask_spread_pct",
        r: {
          value: "total_estimated_trade_volume_usd",
          label: "EST. Trade Vol. (USD)",
        },
        fill: "item_name",
        tip: true,
      }),
    ]
  })
  ```

  ${scatter_plot}

  </div>

  <div class="card">

</div>

<!-- TABLE -->
<div class="card grid-colspan-2" style="padding: 0px">
  <div style="padding: 1em 1em 0">

  ```js
  const searchItems = view(Inputs.search(item_metrics));
  ```

  </div>

```js
const itemsTable = view(Inputs.table(searchItems, {
    value: searchItems.filter(d => selectionMap.has(d.item_name)),
    width: {
      item_name: 300,
    },
    required: false,
    columns: [
      "item_name",
      "ask_count",
      "ask_price_usd",
      "bid_price_usd",
      "bid_ask_spread_pct",
      "units_sold",
      "total_estimated_trade_volume_usd",
      "turnover_rate",
      "bid_ask_ratio",
    ],
    header: {
      item_name: "Item Name",
      units_sold: "Units Sold",
      ask_count: "Ask Count",
      ask_price_usd: "Ask (USD)",
      bid_price_usd: "Bid (USD)",
      bid_ask_spread_pct: "Bid-Ask Spread (%)",
      total_estimated_trade_volume_usd: "Total Est. Trade Volume (USD)",
      turnover_rate: "Turnover Rate",
      bid_ask_ratio: "Bid-Ask Ratio",
    },
    format: {
      ask_price_usd: (d) => d == null ? "N/A" : `$${Number(d).toFixed(2)}`,
      bid_price_usd: (d) => d == null ? "N/A" : `$${Number(d).toFixed(2)}`,
      total_estimated_trade_volume_usd: (d) => d == null ? "N/A" : `$${Number(d).toFixed(2)}`,
      bid_ask_ratio: (d) => d == null ? "N/A" : Number(d).toFixed(2),
      ask_count: (d) => d == null ? "N/A" : d,
      units_sold: (d) => d == null ? "N/A" : d,
      turnover_rate: (d) => d == null ? "N/A" : Number(d).toFixed(2),
    }
  }));
```
</div>
