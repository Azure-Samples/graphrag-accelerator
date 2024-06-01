# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import argparse
import asyncio

from src import main  # noqa: F401
from src.api.index import _start_indexing_pipeline

parser = argparse.ArgumentParser(description="Kickoff indexing job.")
parser.add_argument("-i", "--index-name", required=True)
parser.add_argument("-s", "--storage-name", required=True)
parser.add_argument("-e", "--entity-config", required=False)
args = parser.parse_args()

asyncio.run(
    _start_indexing_pipeline(
        index_name=args.index_name,
        storage_name=args.storage_name,
        entity_config_name=args.entity_config,
    )
)
