# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""
Integration tests for the /health API endpoint.
"""


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
