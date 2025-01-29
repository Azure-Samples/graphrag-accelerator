# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""
Integration tests for the /data API endpoints.
"""

import os

from azure.cosmos import CosmosClient


def test_upload_files(cosmos_client: CosmosClient, client):
    """Test uploading files to a data blob container."""
    # create a single file
    with open("test.txt", "wb") as f:
        f.write(b"Hello, world!")
    # send the file in the request
    with open("test.txt", "rb") as f:
        response = client.post(
            "/data",
            files={"files": ("test.txt", f)},
            params={"container_name": "testContainer"},
        )
    # check the response
    assert response.status_code == 200
    # remove the sample file as part of garbage collection
    if os.path.exists("test.txt"):
        os.remove("test.txt")


def test_delete_files(cosmos_client: CosmosClient, client):
    """Test deleting a data blob container."""
    # delete a data blob container
    response = client.delete("/data/testContainer")
    assert response.status_code == 200


def test_get_list_of_data_containers(cosmos_client: CosmosClient, client):
    """Test getting a list of all data blob containers."""
    response = client.get("/data")
    assert response.status_code == 200
