import json
import re
from datetime import datetime, timezone
from urllib.parse import quote

import dlt
from dlt.sources.helpers import requests
from dlt.sources.rest_api import rest_api_source

BASE_URL = "https://steamcommunity.com/market/"

# Compiled regex to extract price history JS variable from the HTML response
price_history_regex = re.compile(r"var line1=([^;]+);")

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
    f"http://{token}:@proxy.scrape.do:8080" if token else dlt.secrets.get("PROXY_URL")
)
proxy_enabled_session.proxies = {
    "http": f"http://{proxy_url}",
    "https": f"http://{proxy_url}",
}

# Pass the proxied session to rest_api_source
items_data_source = rest_api_source(
    {
        "client": {
            "base_url": BASE_URL,
            "session": proxy_enabled_session,
        },
        "resources": [
            {
                "name": "items",
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
                        "limit": 10,  # pagesize parameter value
                        "offset_param": "start",  # query param name for offset
                        "limit_param": "pagesize",  # query param name for limit
                        "total_path": "total_count",  # JSONPath to total count in response
                    },
                },
            },
        ],
    },
    name="ingest_cs2_items",
)


def add_snapshot_date(item):
    item["snapshot_date"] = datetime.now(timezone.utc).isoformat()
    return item


items_data_source.resources["items"].add_map(add_snapshot_date)


@dlt.transformer(
    name="item_price_history", parallelized=True, write_disposition="append"
)
def extract_price_history(item):
    market_hash_name = item.get("asset_description", {}).get("market_hash_name")
    if not market_hash_name:
        return []

    # Generate the item URL (market_hash_name often needs URL-encoding for the HTTP request)
    url = f"https://steamcommunity.com/market/listings/730/{quote(market_hash_name)}"

    # Fetch html
    response = proxy_enabled_session.get(url)

    if response.status_code == 200:
        # The Steam market price history is stored in a JS variable like: var line1=[["Nov...", 1.2, "5"], ...];
        # We capture everything from `var line1=` up to the trailing `;`
        match = price_history_regex.search(response.text)

        if match:
            json_str = match.group(1)
            try:
                # json.loads perfectly parses valid JS arrays into Python lists
                price_history = json.loads(json_str)

                state = dlt.current.resource_state()
                last_seen_date_str = state.setdefault(market_hash_name, "Jan 01 1970")
                # Steam dates are "Mmm DD YYYY HH: +0" like "Nov 23 2023 01: +0"
                last_seen_date = datetime.strptime(last_seen_date_str, "%b %d %Y")

                new_records = []
                max_date = last_seen_date

                for data_point in price_history:
                    # e.g. "Nov 23 2023 01: +0" -> "Nov 23 2023"
                    current_date_str = data_point[0][:11]
                    current_date = datetime.strptime(current_date_str, "%b %d %Y")

                    if current_date > last_seen_date:
                        new_records.append(
                            {
                                "market_hash_name": market_hash_name,  # parent relation identifier
                                "date": data_point[0],
                                "price": data_point[1],
                                "volume": int(data_point[2]),
                            }
                        )
                        if current_date > max_date:
                            max_date = current_date

                state[market_hash_name] = max_date.strftime("%b %d %Y")

                # Return the list instead of yielding, which is optimal for a thread-pooled transformer function in dlt
                return new_records
            except (json.JSONDecodeError, IndexError, ValueError) as e:
                # TODO: improve error handling/logging here
                print(
                    f"Error occurred while processing price history for {market_hash_name}: {e}"
                )

    return []


pipeline = dlt.pipeline(
    pipeline_name="ingest_cs2_items",
    destination="filesystem",
    dataset_name="cs2_market",
)

items_data_source.resources[
    "items"
]  # Add `.add_limit(2)` to test with fewer items while developing
data_to_load = [
    items_data_source,
    items_data_source | extract_price_history,
]


# DEV:
# $env:DESTINATION__FILESYSTEM__BUCKET_URL="gs://data-lake_test-bucket"
load_info = pipeline.run(
    data_to_load,
    loader_file_format="parquet",
)


print(load_info)
