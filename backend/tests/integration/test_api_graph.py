# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""
Integration tests for the /graph API endpoints.
"""


def test_get_graphml_file(client, container_with_graphml_file: str):
    """Test retrieving a graphml file endpoint."""
    url = f"/graph/graphml/{container_with_graphml_file}"
    response = client.get(url)
    assert response.status_code == 200
    response.raise_for_status()
    full_data = b""
    for chunk in response.iter_bytes(chunk_size=1024):
        full_data += chunk
    assert full_data == b"a fake graphml file"
