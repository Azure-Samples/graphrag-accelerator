# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from azure.cosmos import CosmosClient
from azure.storage.blob import BlobServiceClient
from azure.storage.blob.aio import BlobServiceClient as BlobServiceClientAsync

from graphrag_app.utils.azure_clients import (
    AzureClientManager,
    _BlobServiceClientSingleton,
    _BlobServiceClientSingletonAsync,
    _CosmosClientSingleton,
)


def test_get_cosmos_singleton():
    """verify correctness of singleton implementation"""
    client1 = _CosmosClientSingleton.get_instance()
    client2 = _CosmosClientSingleton.get_instance()
    assert isinstance(client1, CosmosClient)
    assert isinstance(client2, CosmosClient)
    assert client1 is client2


def test_get_storage_singleton():
    """Verify correctness of singleton implementation"""
    client1 = _BlobServiceClientSingleton.get_instance()
    client2 = _BlobServiceClientSingleton.get_instance()
    assert isinstance(client1, BlobServiceClient)
    assert isinstance(client2, BlobServiceClient)
    assert client1 is client2  # check if both reference the same object


def test_get_storage_async_singleton():
    """Verify correctness of singleton implementation"""
    client1 = _BlobServiceClientSingletonAsync.get_instance()
    client2 = _BlobServiceClientSingletonAsync.get_instance()
    assert isinstance(client1, BlobServiceClientAsync)
    assert isinstance(client2, BlobServiceClientAsync)
    assert client1 is client2  # check if both reference the same object


def test_azure_client_manager():
    azure_client_manager = AzureClientManager()
    assert isinstance(azure_client_manager, AzureClientManager)
    assert isinstance(azure_client_manager.get_cosmos_client(), CosmosClient)
    assert isinstance(azure_client_manager.get_blob_service_client(), BlobServiceClient)
    assert isinstance(
        azure_client_manager.get_blob_service_client_async(), BlobServiceClientAsync
    )
