# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""
Integration tests for the /index API endpoints.
"""

from azure.cosmos import CosmosClient


def test_get_list_of_index_containers_empty(client, cosmos_client: CosmosClient):
    """Test getting a list of all blob containers holding an index."""
    response = client.get("/index")
    assert response.status_code == 200


def test_schedule_index_without_data(client, cosmos_client: CosmosClient):
    """Test scheduling an index job with a non-existent data blob container."""
    response = client.post(
        "/index",
        params={
            "index_container_name": "myindex",
            "storage_container_name": "nonexistent-data-container",
        },
    )
    assert response.status_code == 500


# def test_schedule_index_with_data(client, cosmos_client, blob_with_data_container_name):
#     """Test scheduling an index job with real data."""
#     response = client.post("/index", files=None, params={"storage_container_name": blob_with_data_container_name, "index_container_name": "myindex"})
#     print(response.json())
#     assert response.status_code == 200
