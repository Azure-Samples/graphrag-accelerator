import os

from azure.cosmos import CosmosClient
from azure.storage.blob import BlobServiceClient

from src.api.azure_clients import (
    AzureClientManager,
    BlobServiceClientSingleton,
    CosmosClientSingleton,
)


def test_get_env_variables():
    print(f"\nCOSMOS CONNECTION STRING: {os.getenv('COSMOS_CONNECTION_STRING')}")
    print(f"STORAGE CONNECTION STRING: {os.getenv('STORAGE_CONNECTION_STRING')}")
    assert os.getenv("COSMOS_CONNECTION_STRING") is not None
    assert os.getenv("STORAGE_CONNECTION_STRING") is not None


def test_get_cosmos_singleton():
    client = CosmosClientSingleton.get_instance()
    assert isinstance(
        client, CosmosClient
    )  # may or may not be the correct way to verify the client was created successfully


def test_get_storage_singleton():
    client = BlobServiceClientSingleton.get_instance()
    assert isinstance(
        client, BlobServiceClient
    )  # may or may not be the correct way to verify the client was created successfully


def test_get_azure_client_manager():
    client_manager = AzureClientManager()
    assert isinstance(
        client_manager, AzureClientManager
    )  # may or may not be the correct way to verify the client was created successfully
