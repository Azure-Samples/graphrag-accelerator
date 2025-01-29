# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""
Integration tests for the /source API endpoints.
"""

from fastapi.testclient import TestClient


def test_get_report(container_with_index_files: str, client: TestClient):
    """Test retrieving a report via the graphrag_app.api.source.get_report_info() function."""
    # retrieve a report that exists
    response = client.get(f"/source/report/{container_with_index_files}/1")
    assert response.status_code == 200
    # # retrieve a report that does not exist
    # response = client.get(f"/source/report/{container_with_index_files}/-1")
    # assert response.status_code == 500


def test_get_chunk_info(container_with_index_files: str, client: TestClient):
    """Test retrieving a text chunk."""
    response = client.get(
        f"/source/text/{container_with_index_files}/c4197a012ea9e7d2618450cbb197852dec47c40883d4a69e0ea473a8111319c80d608ae5fa66acc2d3f95cd845277b3acd8186d7fa326803dde09681da29790c"
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
