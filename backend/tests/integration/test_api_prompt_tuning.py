# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""
Integration tests for the /index/config API endpoints.
"""

from unittest.mock import AsyncMock, patch

import pytest_asyncio


@pytest_asyncio.fixture
def mock_generate_indexing_prompts():
    with patch(
        "graphrag.api.generate_indexing_prompts", new_callable=AsyncMock
    ) as mock:
        mock.return_value = (
            "synthetic-prompt1",
            "synthetic-prompt2",
            "synthetic-prompt3",
        )
        yield mock


def test_generate_prompts(
    blob_with_data_container_name, mock_generate_indexing_prompts, client
):
    """Test generating prompts."""
    response = client.get(
        "/index/config/prompts",
        params={"container_name": blob_with_data_container_name},
    )
    assert response.status_code == 200
