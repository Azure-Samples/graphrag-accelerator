# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import argparse
import asyncio

from src import main  # noqa: F401
from src.api.index import _start_indexing_pipeline

parser = argparse.ArgumentParser(description="Kickoff indexing job.")
parser.add_argument("-i", "--index-name", required=True)
args = parser.parse_args()

asyncio.run(
    _start_indexing_pipeline(
        index_name=args.index_name,
    )
)
