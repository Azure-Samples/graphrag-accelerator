# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from unittest.mock import patch

from azure.cosmos import (
    ContainerProxy,
    CosmosClient,
    DatabaseProxy,
)
from azure.storage.blob import BlobServiceClient
from azure.storage.blob.aio import BlobServiceClient as BlobServiceClientAsync
from src.api.azure_clients import AzureStorageClientManager


class TestAzureStorageClientManager:
    @patch("src.api.azure_clients.BlobServiceClientAsync.from_connection_string")
    @patch("src.api.azure_clients.BlobServiceClient.from_connection_string")
    @patch("src.api.azure_clients.CosmosClient.from_connection_string")
    def get_azure_storage_client_manager(
        self,
        mock_cosmos_client,
        mock_blob_service_client,
        mock_blob_service_client_async,
    ):
        mock_blob_service_client.return_value = BlobServiceClient
        mock_blob_service_client_async.return_value = BlobServiceClientAsync
        mock_cosmos_client.return_value = CosmosClient
        manager = AzureStorageClientManager()
        return manager

    def test_get_blob_service_client(self):
        manager = self.get_azure_storage_client_manager()
        client = manager.get_blob_service_client()
        assert client == BlobServiceClient

    def test_get_blob_service_client_async(self):
        manager = self.get_azure_storage_client_manager()
        client = manager.get_blob_service_client_async()
        assert client == BlobServiceClientAsync

    def test_get_cosmos_client(self):
        manager = self.get_azure_storage_client_manager()
        client = manager.get_cosmos_client()
        assert client == CosmosClient

    @patch("src.api.azure_clients.CosmosClient.get_database_client")
    def test_get_cosmos_database_client(self, mock_get_database_client):
        mock_get_database_client.return_value = DatabaseProxy
        manager = self.get_azure_storage_client_manager()
        db_name = "test_database"
        client = manager.get_cosmos_database_client(db_name)
        assert client == DatabaseProxy

    @patch("src.api.azure_clients.DatabaseProxy.get_container_client")
    @patch("src.api.azure_clients.CosmosClient.get_database_client")
    def test_get_cosmos_container_client(
        self, mock_get_database_client, mock_get_container_client
    ):
        mock_get_database_client.return_value = DatabaseProxy
        mock_get_container_client.return_value = ContainerProxy
        manager = self.get_azure_storage_client_manager()
        database_name = "test_database"
        container_name = "test_container"
        client = manager.get_cosmos_container_client(
            database_name=database_name, container_name=container_name
        )
        assert client == manager._cosmos_client.get_database_client(
            database_name
        ).get_container_client(container_name)
