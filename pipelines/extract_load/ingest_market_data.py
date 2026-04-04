import json
import re
from datetime import datetime, timezone
from typing import Annotated, Iterator, TypedDict
from urllib.parse import quote

import dlt
from dlt.destinations.adapters import bigquery_adapter
from dlt.sources.helpers import requests
from dlt.sources.rest_api import rest_api_source
from dlthub._runner.prefect_collector import PrefectCollector

STACK: str = dlt.secrets.get("PULUMI_STACK") or "dev"
BASE_URL = "https://steamcommunity.com/market/"

# Compiled regex to extract price history JS variable from the HTML response
PRICE_HISTORY_REGEX = re.compile(r"var line1=([^;]+);")

# Create a custom session with proxy settings
proxy_enabled_session = requests.Client(
    request_timeout=(5.0, 15.0),  # (connect_timeout, read_timeout)
    request_max_attempts=3,
).session

# set to false to let dlt handle http errors gracefully
proxy_enabled_session.raise_for_status = False

# Configure proxies on the session
token = dlt.secrets.get("PROXY_TOKEN")
proxy_url = (
    # Use scrape.do proxy if user provided their token...
    f"http://{token}:@proxy.scrape.do:8080"
    if token
    # otherwise we use the proxy URL provided by the user in the PROXY_URL secret
    else dlt.secrets.get("PROXY_URL")
)

proxy_enabled_session.proxies = {
    "http": f"http://{proxy_url}",
    "https": f"http://{proxy_url}",
}

# Global snapshot date to ensure consistency across all records in a single run.
# This avoids multiple calls to datetime.now() and ensures all item metadata
# belongs to the same logical batch.
GLOBAL_SNAPSHOT_DATE = None

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
    name="ingest_cs2_items",
)


def add_snapshot_date(item):
    # Use the global batch timestamp
    item["snapshot_date"] = GLOBAL_SNAPSHOT_DATE
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


items_data_source.resources["items_raw"].add_map(add_snapshot_date)
items_data_source.resources["items_raw"].add_map(remove_redundant_columns)

bigquery_adapter(
    items_data_source.resources["items_raw"],
    partition="snapshot_date",
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
    write_disposition="merge",
    primary_key=["market_hash_name", "date"],
)
def extract_median_price_sale_history(item) -> Iterator[PriceRecord]:
    """Extracts the median sale prices for a given market item"""
    market_hash_name = item.get("asset_description", {}).get("market_hash_name")
    if not market_hash_name:
        return

    url = f"https://steamcommunity.com/market/listings/730/{quote(market_hash_name)}"
    response = proxy_enabled_session.get(url)

    if response.status_code == 200:
        match = PRICE_HISTORY_REGEX.search(response.text)
        if match:
            json_str = match.group(1)
            try:
                price_history = json.loads(json_str)

                # State tracking per item hash name
                state = dlt.current.resource_state()
                last_seen_date_str = state.get(market_hash_name, "Jan 01 1970")
                last_seen_date = datetime.strptime(last_seen_date_str, "%b %d %Y")

                max_date = last_seen_date

                for data_point in price_history:
                    current_date_str = data_point[0][:11]
                    current_date = datetime.strptime(current_date_str, "%b %d %Y")

                    if current_date > last_seen_date:
                        # Yielding records one by one is most memory efficient at scale
                        yield {
                            "market_hash_name": market_hash_name,
                            "date": current_date,
                            "price": float(data_point[1]),
                            "volume": int(data_point[2]),
                        }
                        if current_date > max_date:
                            max_date = current_date

                # Persistence of state happens automatically after successful dlt load
                state[market_hash_name] = max_date.strftime("%b %d %Y")

            except (json.JSONDecodeError, IndexError, ValueError) as e:
                print(f"Error processing {market_hash_name}: {e}")


def run_ingest():
    # Set the logical timestamp for the entire batch.
    # We keep the full timestamp to allow for future intra-day run support.
    global GLOBAL_SNAPSHOT_DATE
    GLOBAL_SNAPSHOT_DATE = datetime.now(timezone.utc)

    pipeline = dlt.pipeline(
        pipeline_name="ingest_cs2_items",
        destination="bigquery",
        staging="filesystem",
        dataset_name=f"cs2_market_dwh_{STACK}",
        progress=PrefectCollector(),
    )

    # TODO: remove after finished with development
    items_data_source.resources["items_raw"].add_limit(1)

    # Apply BigQuery-specific hints to transformer output
    item_price_history_configured = bigquery_adapter(
        extract_median_price_sale_history,
        partition="date",
        cluster=["market_hash_name"],
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
    print(run_ingest())
