# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import inspect
import os
from typing import Generator

import pytest
from azure.cosmos import CosmosClient, PartitionKey
from azure.storage.blob import BlobServiceClient
from fastapi.testclient import TestClient

from src.api.common import sanitize_name
from src.main import app


@pytest.fixture(scope="session")
def blob_with_data_container_name(blob_service_client: BlobServiceClient):
    # create a storage container and upload some data
    container_name = "container-with-data"
    blob_service_client.create_container(container_name)
    blob_client = blob_service_client.get_blob_client(container_name, "data.txt")
    blob_client.upload_blob(data="Hello, World!", overwrite=True)
    yield container_name
    # cleanup
    blob_service_client.delete_container(container_name)


@pytest.fixture(scope="session")
def blob_service_client() -> Generator[BlobServiceClient, None, None]:
    blob_service_client = BlobServiceClient.from_connection_string(
        os.environ["STORAGE_CONNECTION_STRING"]
    )
    yield blob_service_client
    # no cleanup


@pytest.fixture(scope="session")
def cosmos_client() -> Generator[CosmosClient, None, None]:
    """Initializes the CosmosDB databases that graphrag expects at startup time."""
    # setup
    client = CosmosClient.from_connection_string(os.environ["COSMOS_CONNECTION_STRING"])
    db_client = client.create_database_if_not_exists(id="graphrag")
    db_client.create_container_if_not_exists(
        id="container-store", partition_key=PartitionKey(path="/id")
    )
    db_client.create_container_if_not_exists(
        id="jobs", partition_key=PartitionKey(path="/id")
    )
    yield client  # run the test
    # teardown
    client.delete_database("graphrag")


@pytest.fixture(scope="session")
def container_with_graphml_file(
    blob_service_client: BlobServiceClient, cosmos_client: CosmosClient
):
    """Create a storage container that mimics a valid index and upload a fake graphml file"""
    container_name = "container-with-graphml"
    sanitized_name = sanitize_name(container_name)
    if not blob_service_client.get_container_client(sanitized_name).exists():
        blob_service_client.create_container(sanitized_name)
    blob_client = blob_service_client.get_blob_client(
        sanitized_name, "output/summarized_graph.graphml"
    )
    blob_client.upload_blob(data="a fake graphml file", overwrite=True)
    # add an entry to the container-store table in cosmos db
    container_store_client = cosmos_client.get_database_client(
        "graphrag"
    ).get_container_client("container-store")
    container_store_client.upsert_item({
        "id": sanitized_name,
        "human_readable_name": container_name,
        "type": "index",
    })
    yield container_name
    # cleanup
    blob_service_client.delete_container(sanitized_name)
    # container_store_client.delete_item(sanitized_name, sanitized_name)


@pytest.fixture(scope="session")
def container_with_index_files(
    blob_service_client: BlobServiceClient, cosmos_client: CosmosClient
):
    """Create a storage container and upload a set of parquet files associated with a valid index"""
    container_name = "container-with-index-files"
    sanitized_name = sanitize_name(container_name)
    if not blob_service_client.get_container_client(sanitized_name).exists():
        blob_service_client.create_container(sanitized_name)

    # upload data/aliens-dataset/output folder to the container
    this_directory = os.path.dirname(
        os.path.abspath(inspect.getfile(inspect.currentframe()))
    )
    data_root = f"{this_directory}/data/synthetic-dataset/output"
    for file in [
        "create_base_documents.parquet",
        "create_final_entities.parquet",
        "create_final_relationships.parquet",
        "create_final_community_reports.parquet",
        "create_base_text_units.parquet",
    ]:
        blob_client = blob_service_client.get_blob_client(
            sanitized_name, f"output/{file}"
        )
        local_file = f"{data_root}/{file}"
        with open(local_file, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)

    # add an entry to the container-store table in cosmos db
    container_store_client = cosmos_client.get_database_client(
        "graphrag"
    ).get_container_client("container-store")
    container_store_client.upsert_item({
        "id": sanitized_name,
        "human_readable_name": container_name,
        "type": "index",
    })
    yield container_name
    # cleanup
    blob_service_client.delete_container(sanitized_name)
    container_store_client.delete_item(sanitized_name, sanitized_name)


@pytest.fixture(scope="session")
def client(request) -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c
