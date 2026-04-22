import os
import sys
from io import BytesIO

import pyarrow as pa
import pyarrow.parquet as pq
from google.cloud import storage


def load_parquet(export_folder: str) -> None:
    """
    Downloads all parquet files from a GCS dashboard export location,
    merges them, and writes a single valid parquet stream to stdout.

    Args:
        export_folder: The name of the export folder (e.g. 'item_group_summary')
    """
    project = os.environ.get("GOOGLE_PROJECT")
    stack = os.environ.get("PULUMI_STACK", "dev")

    if not project:
        print("GOOGLE_PROJECT environment variable is missing.", file=sys.stderr)
        sys.exit(1)

    bucket_name = f"{project}-cs2-data-lake-{stack}"
    prefix = f"dashboard-exports/{export_folder}/"

    try:
        client = storage.Client(project=project)
        bucket = client.bucket(bucket_name)

        blobs = list(bucket.list_blobs(prefix=prefix))
        parquet_blobs = [b for b in blobs if b.name.endswith(".parquet")]

        if not parquet_blobs:
            print(
                f"No parquet files found in gs://{bucket_name}/{prefix}",
                file=sys.stderr,
            )
            sys.exit(1)

        # 1. Download and read each sharded parquet file
        tables = []
        for blob in parquet_blobs:
            # Read bytes into an Arrow table
            table = pq.read_table(BytesIO(blob.download_as_bytes()))
            tables.append(table)

        # 2. Concatenate them into a single valid Arrow table
        combined_table = pa.concat_tables(tables)

        # 3. Write the unified table out to stdout as a single Parquet file
        pq.write_table(combined_table, sys.stdout.buffer)

    except Exception as e:
        print(f"Failed to load parquet data for {export_folder}: {e}", file=sys.stderr)
        sys.exit(1)
