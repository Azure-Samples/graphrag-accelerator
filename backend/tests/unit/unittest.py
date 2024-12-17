from unittest.mock import MagicMock

import pytest
from azure.storage.blob import BlobClient, BlobServiceClient, ContainerClient


@pytest.fixture
def mock_blob_service_client(mocker):
    # Mock the from_connection_string method
    mock_from_connection_string = mocker.patch(
        "azure.storage.blob.BlobServiceClient.from_connection_string"
    )

    # Create a mock BlobServiceClient
    mock_blob_service_client = MagicMock(spec=BlobServiceClient)
    mock_from_connection_string.return_value = mock_blob_service_client

    # Create a mock ContainerClient
    mock_container_client = MagicMock(spec=ContainerClient)
    mock_blob_service_client.get_container_client.return_value = mock_container_client

    # Create a mock BlobClient
    mock_blob_client = MagicMock(spec=BlobClient)
    mock_container_client.get_blob_client.return_value = mock_blob_client

    return mock_blob_service_client


def test_upload_blob(mock_blob_service_client):
    # Arrange
    blob_service_client = BlobServiceClient.from_connection_string(
        "fake_connection_string"
    )
    container_client = blob_service_client.get_container_client("mycontainer")
    blob_client = container_client.get_blob_client("myblob")

    # Act
    blob_client.upload_blob(b"Hello, World!")

    # Assert
    blob_client.upload_blob.assert_called_once_with(b"Hello, World!")


def test_download_blob(mock_blob_service_client):
    # Arrange
    blob_service_client = BlobServiceClient.from_connection_string(
        "fake_connection_string"
    )
    container_client = blob_service_client.get_container_client("mycontainer")
    blob_client = container_client.get_blob_client("myblob")

    # Mock the download_blob method
    blob_client.download_blob.return_value.readall.return_value = b"Hello, World!"

    # Act
    data = blob_client.download_blob().readall()

    # Assert
    assert data == b"Hello, World!"
    blob_client.download_blob.assert_called_once()
