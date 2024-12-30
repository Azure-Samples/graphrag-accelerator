# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""
Integration tests for the /source API endpoints.
"""

from fastapi.testclient import TestClient


def test_get_report(container_with_index_files: str, client: TestClient):
    """Test retrieving a report via the src.api.source.get_report_info() function."""
    # retrieve a report that exists
    response = client.get(f"/source/report/{container_with_index_files}/1")
    assert response.status_code == 200
    # # retrieve a report that does not exist
    # response = client.get(f"/source/report/{container_with_index_files}/-1")
    # assert response.status_code == 500


def test_get_chunk_info(container_with_index_files: str, client: TestClient):
    """Test retrieving a text chunk."""
    response = client.get(
        f"/source/text/{container_with_index_files}/5b2d21ec6fc171c30bdda343f128f5a6"
    )
    assert response.status_code == 200


def test_get_entity_info(container_with_index_files: str, client: TestClient):
    """Test retrieving an entity description."""
    response = client.get(f"/source/entity/{container_with_index_files}/1")
    assert response.status_code == 200


def test_get_relationship_info(container_with_index_files: str, client: TestClient):
    """Test retrieving an entity description."""
    response = client.get(f"/source/relationship/{container_with_index_files}/1")
    assert response.status_code == 200
