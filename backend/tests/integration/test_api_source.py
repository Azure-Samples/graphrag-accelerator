# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""
Integration tests for the /source API endpoints.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_community_report_dataframe():
    """Mock a pandas Dataframe that represents a community report."""
    with patch("src.api.source.pd.read_parquet") as mock_read_parquet:
        mock_df = MagicMock(spec=pd.DataFrame)
        mock_df.loc.__getitem__.return_value = MagicMock()
        mock_df.loc.__getitem__.return_value.__getitem__.return_value = (
            "This is content for a test report"
        )
        mock_read_parquet.return_value = mock_df
        yield mock_read_parquet


@pytest.mark.skip(reason="temporary skip")
def test_get_report(
    container_with_index_files: str, client: TestClient, mock_community_report_dataframe
):
    """Test deleting a data blob container."""
    # delete a data blob container
    response = client.get(f"/source/report/{container_with_index_files}/1")
    assert response.status_code == 200


# @pytest.fixture
# def mock_text_unit_dataframe():
#     """Mock a pandas Dataframe that represents text units."""
#     with patch('src.api.source.pd.read_parquet') as mock_read_parquet:
#         mock_df = MagicMock(spec=pd.DataFrame)
#         mock_df.loc.__getitem__.return_value = MagicMock()
#         mock_df.loc.__getitem__.return_value.__getitem__.return_value = "This is content for a test text unit"
#         mock_read_parquet.return_value = mock_df
#         yield mock_read_parquet


# @pytest.fixture
# def mock_documents_dataframe():
#     """Mock a pandas Dataframe that represents documents."""
#     with patch('src.api.source.pd.read_parquet') as mock_read_parquet:
#         mock_df = MagicMock(spec=pd.DataFrame)
#         mock_df.loc.__getitem__.return_value = MagicMock()
#         mock_df.loc.__getitem__.return_value.__getitem__.return_value = "This is content for a test document"
#         mock_read_parquet.return_value = mock_df
#         yield mock_read_parquet


# def test_get_chunk_info(container_with_index_files: str, client: TestClient, mock_text_unit_dataframe, mock_documents_dataframe):
#     """Test retrieving a text chunk."""
#     response = client.get(f"/source/text/{container_with_index_files}/1")
#     assert response.status_code == 200
