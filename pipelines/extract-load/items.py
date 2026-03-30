import dlt
from dlt.sources.helpers import requests
from dlt.sources.rest_api import rest_api_source

BASE_URL = "https://steamcommunity.com/market/"  # search/render/?query=&start=0&count=10&search_descriptions=0&sort_column=name&sort_dir=asc&appid=730&norender=1
PARAMS = {
    "query": "",
    "search_descriptions": 0,
    "sort_column": "name",
    "sort_dir": "asc",
    "appid": 730,
    "norender": 1,
}

# Create a custom session with proxy settings
custom_session = requests.Client(
    request_timeout=(5.0, 15.0),  # (connect_timeout, read_timeout)
    request_max_attempts=3,
).session

proxy_url = "YOUR-PROXY-URL-HERE"  # TODO: find a way to pass this in securely
# Configure proxies on the session
custom_session.proxies = {
    "http": f"http://{proxy_url}",
    "https": f"http://{proxy_url}",
}

# set to false to let dlt handle http errors gracefully
custom_session.raise_for_status = False

# Pass the proxied session to rest_api_source
source = rest_api_source(
    {
        "client": {
            "base_url": BASE_URL,
            # "session": custom_session,  # TODO: Uncomment for prod
            "paginator": {
                "type": "offset",
                "limit": 10,  # pagesize parameter value
                "offset_param": "start",  # query param name for offset
                "limit_param": "pagesize",  # query param name for limit
                "total_path": "total_count",  # JSONPath to total count in response
            },
        },
        "resources": [
            {
                "name": "items",
                "endpoint": {
                    "path": "search/render/",
                    "data_selector": "results",
                    "params": PARAMS,
                },
            }
        ],
    }
)

pipeline = dlt.pipeline(
    pipeline_name="ingest_cs2_items",
    destination="filesystem",
    dataset_name="cs2_market_data",
)


# TODO: uncomment and cleanup for prod
# PROD:
# load_info = pipeline.run(source)

# DEV:
# $env:DESTINATION__FILESYSTEM__BUCKET_URL="gs://data-lake_test-bucket"
load_info = pipeline.run(
    source.add_limit(1), write_disposition="replace", dataset_name="dev"
)


print(load_info)
