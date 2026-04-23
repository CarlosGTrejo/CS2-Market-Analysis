import logging
import os
import re
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Annotated, TypedDict
from urllib.parse import quote

import dlt
import orjson as json  # drop in replacement, faster than built-in json and compatible with dlt's JSON handling
from dlt.destinations.adapters import bigquery_adapter
from dlt.sources.helpers import requests
from dlt.sources.rest_api import rest_api_source
from dlthub._runner.prefect_collector import PrefectCollector

logger = logging.getLogger("dlt")

STACK: str = os.getenv("PULUMI_STACK", "dev")
BASE_URL = "https://steamcommunity.com/market/"

# Compiled regex to extract price history JS variable from the HTML response
PRICE_HISTORY_REGEX = re.compile(r"var line1=([^;]+);")

# Create a custom session with proxy settings
proxy_enabled_session = requests.Client(
    request_timeout=(5.0, 15.0),  # (connect_timeout, read_timeout)
    request_max_attempts=7,  # Increased to allow for resilient backoff on 429s (max 7 attempts)
    raise_for_status=False,
    max_connections=60,  # Increase pool size to allow up to 60 concurrent connections
).session

# Configure proxies on the session
proxy_url = dlt.secrets.get("PROXY_URL")
if not proxy_url:
    raise ValueError("PROXY_URL is not set, please specify a proxy URL.")

proxy_enabled_session.proxies = {
    "http": f"http://{proxy_url}",
    "https": f"http://{proxy_url}",
}

proxy_enabled_session.headers.update(
    {
        "Referer": "https://steamcommunity.com/market/search?appid=730",
        "Accept-Language": "en-US,en;q=0.9",
    }
)

# Global snapshot date to ensure consistency across all records in a single run.
# This avoids multiple calls to datetime.now() and ensures all item metadata
# belongs to the same logical batch. ContextVar makes it safe for concurrent runs.
GLOBAL_SNAPSHOT_TIMESTAMP: ContextVar[datetime] = ContextVar("snapshot_timestamp")

# Using two separate resources (items and item_price_history) is the best approach.
# It avoids emitting redundant item data for each price/volume datapoint,
# keeping the history table lean and the metadata table normalized.
items_data_source = rest_api_source(
    {
        "client": {
            "base_url": BASE_URL,
            "session": proxy_enabled_session,
        },
        "resource_defaults": {
            "write_disposition": "append",
        },
        "resources": [
            {
                "name": "items_raw",
                "endpoint": {
                    "path": "search/render/",
                    "data_selector": "results",
                    "params": {
                        "query": "",
                        "search_descriptions": 0,
                        "sort_column": "name",
                        "sort_dir": "asc",
                        "appid": 730,
                        "norender": 1,
                    },
                    "paginator": {
                        "type": "offset",
                        "limit": 10,
                        "offset_param": "start",
                        "limit_param": "pagesize",
                        "total_path": "total_count",
                    },
                },
            },
        ],
    },
    name="items",
)


def add_snapshot_timestamp(item):
    # Use the global batch timestamp (thread-safe)
    item["snapshot_timestamp"] = GLOBAL_SNAPSHOT_TIMESTAMP.get()
    return item


def remove_redundant_columns(item):
    """
    Prune redundant fields to save memory and network bandwidth.
    Duplicate fields (keeping only market_hash_name):
    - name
    - hash_name
    - asset_description.name
    - asset_description.market_name

    Redundant fields (these add no value to our analysis, and are the same across all items, so we can safely remove them):
    - app_icon
    - app_name
    - asset_description.app_id
    - asset_description.icon_url
    """
    item.pop("name", None)
    item.pop("hash_name", None)
    item.pop("app_icon", None)
    item.pop("app_name", None)
    asset = item.get("asset_description", {})
    if asset:
        asset.pop("name", None)
        asset.pop("market_name", None)
        asset.pop("appid", None)
        asset.pop("icon_url", None)
    return item


items_data_source.resources["items_raw"].add_map(add_snapshot_timestamp)
items_data_source.resources["items_raw"].add_map(remove_redundant_columns)

bigquery_adapter(
    items_data_source.resources["items_raw"],
    partition="snapshot_timestamp",
    cluster=["asset_description__market_hash_name"],
)


# Define the schema for price history records using TypedDict and Annotated hints.
# Using NUMERIC for price ensures currency precision in BigQuery.
# Using INT64 for volume for optimal storage.
class PriceRecord(TypedDict):
    market_hash_name: str
    date: Annotated[datetime, {"data_type": "timestamp"}]
    price: Annotated[float, {"data_type": "DECIMAL"}]
    volume: Annotated[int, {"data_type": "INT64"}]


@dlt.transformer(
    name="item_price_history_raw",
    parallelized=True,  # Parallelize network-heavy scraping
    write_disposition="append",  # We already track the last seen date, so we can safely append new records without deduplication
    primary_key=["market_hash_name", "date"],
)
def extract_median_price_sale_history(item) -> list[PriceRecord]:
    """Extracts the median sale prices for a given market item"""
    market_hash_name = item.get("asset_description", {}).get("market_hash_name")
    if not market_hash_name:
        return []  # <-- Return empty list instead of empty yield

    url = f"https://steamcommunity.com/market/listings/730/{quote(market_hash_name)}"
    response = proxy_enabled_session.get(url)

    if response.status_code == 200:
        match = PRICE_HISTORY_REGEX.search(response.text)
        if match:
            try:
                price_history = json.loads(match.group(1))

                # State tracking per item hash name
                state = dlt.current.resource_state()
                last_seen_date_str = state.get(market_hash_name, "Jan 01 1970")
                last_seen_date = datetime.strptime(last_seen_date_str, "%b %d %Y")

                max_date = last_seen_date

                # 1. Initialize an empty list to hold our batch of records
                new_records = []

                # 2. Iterate backwards to short-circuit the loop quickly
                for data_point in reversed(price_history):
                    current_date_str = data_point[0][:11]
                    current_date = datetime.strptime(current_date_str, "%b %d %Y")

                    if current_date <= last_seen_date:
                        break  # We've hit data we already have; stop parsing

                    # 3. Append to the list instead of yielding
                    new_records.append(
                        {
                            "market_hash_name": market_hash_name,
                            "date": current_date,
                            "price": float(data_point[1]),
                            "volume": int(data_point[2]),
                        }
                    )

                    if current_date > max_date:
                        max_date = current_date

                # Persistence of state happens automatically after successful dlt load
                if new_records:
                    state[market_hash_name] = max_date.strftime("%b %d %Y")

                # 4. Return the complete list at the very end
                return new_records

            except (json.JSONDecodeError, IndexError, ValueError) as e:
                logger.error(f"Error processing {market_hash_name}: {e}")
    elif response.status_code == 429:
        logger.error(
            f"Rate limited (429) fetching {market_hash_name} after all retries exhausted."
        )
    elif response.status_code == 403:
        logger.error(
            f"Access forbidden (403) for {market_hash_name}. The proxy may be blocked."
        )
    elif response.status_code == 404:
        logger.warning(
            f"Item not found (404) for {market_hash_name}. It may have been removed."
        )
    else:
        logger.error(
            f"Failed to fetch price history for {market_hash_name}. Status code: {response.status_code}"
        )
    return []  # Ensure we always return a list, even on errors/misses


def run_ingest():
    # Set the logical timestamp for the entire batch in the execution context.
    # We keep the full timestamp to allow for future intra-day run support.
    GLOBAL_SNAPSHOT_TIMESTAMP.set(datetime.now(timezone.utc))

    if STACK != "prod":
        # Limit non-prod runs to 10 pages (100 items) for testing and to avoid unnecessary API calls during development
        items_data_source.resources["items_raw"].add_limit(10)
        # Set progress to logging for non-prod to view detailed progress without throwing errors for PrefectCollector.
        PROGRESS = dlt.progress.log(dump_system_stats=False)
    else:
        PROGRESS = PrefectCollector()

    pipeline = dlt.pipeline(
        pipeline_name=f"ingest_market_data_{STACK}",
        destination="bigquery",
        staging="filesystem",
        dataset_name=os.getenv("BQ_DATASET_NAME", f"cs2_market_dwh_{STACK}"),
        progress=PROGRESS,
    )

    # Apply BigQuery-specific hints to transformer output
    item_price_history_configured = bigquery_adapter(
        extract_median_price_sale_history,
        cluster=["market_hash_name", "date"],
    )

    data_to_load = [
        items_data_source,
        items_data_source | item_price_history_configured,
    ]

    load_info = pipeline.run(
        data_to_load,
        loader_file_format="parquet",
    )

    return load_info


if __name__ == "__main__":
    run_ingest()
