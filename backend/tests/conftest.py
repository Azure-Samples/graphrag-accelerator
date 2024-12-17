import os
from typing import Generator

import pytest
from azure.cosmos import CosmosClient, PartitionKey
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture(scope="session")
def setup_cosmos():
    """ "Initializes the CosmosDB databases that graphrag expects at startup time."""
    # setup
    client = CosmosClient.from_connection_string(os.environ["COSMOS_CONNECTION_STRING"])
    db_client = client.create_database_if_not_exists(id="graphrag")
    db_client.create_container_if_not_exists(
        id="container-store", partition_key=PartitionKey(path="/id")
    )
    db_client.create_container_if_not_exists(
        id="jobs", partition_key=PartitionKey(path="/id")
    )
    yield  # run the test
    # teardown
    client.delete_database("graphrag")


@pytest.fixture(scope="session")
def client(request) -> Generator:
    with TestClient(app) as c:
        yield c
