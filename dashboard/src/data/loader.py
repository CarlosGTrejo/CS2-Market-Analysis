import os
import sys

from google.cloud import storage


def load_parquet(export_name: str) -> None:
    """
    Downloads a single parquet file from a GCS dashboard export location
    and writes it directly to stdout.

    Args:
        export_name: The name of the export folder (e.g. 'item_group_summary')
    """
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    stack = os.environ.get("PULUMI_STACK", "dev")

    if not project:
        print("GOOGLE_CLOUD_PROJECT environment variable is missing.", file=sys.stderr)
        sys.exit(1)

    bucket_name = f"{project}-cs2-data-lake-{stack}"
    prefix = f"dashboard-exports/{export_name}/"

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

        sys.stdout.buffer.write(parquet_blobs[0].download_as_bytes())

    except Exception as e:
        print(f"Failed to load parquet data for {export_name}: {e}", file=sys.stderr)
        sys.exit(1)
