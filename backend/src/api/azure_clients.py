# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os

from azure.cosmos import (
    ContainerProxy,
    CosmosClient,
    DatabaseProxy,
)
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from azure.storage.blob.aio import BlobServiceClient as BlobServiceClientAsync
from environs import Env

ENDPOINT_ERROR_MSG = "Could not find connection string in environment variables"

from dotenv import load_dotenv

load_dotenv()


class CosmosClientSingleton:
    _instance = None
    _env = Env()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            endpoint = os.environ["COSMOS_URI_ENDPOINT"]
            credential = DefaultAzureCredential()
            cls._instance = CosmosClient(endpoint, credential)
        return cls._instance


class BlobServiceClientSingleton:
    _instance = None
    _env = Env()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            account_url = os.environ["STORAGE_ACCOUNT_BLOB_URL"]
            credential = DefaultAzureCredential()
            cls._instance = BlobServiceClient(account_url, credential=credential)
        return cls._instance

    @classmethod
    def get_storage_account_name(cls):
        account_url = os.environ["STORAGE_ACCOUNT_BLOB_URL"]
        return account_url.split("//")[1].split(".")[0]


class BlobServiceClientSingletonAsync:
    _instance = None
    _env = Env()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            account_url = os.environ["STORAGE_ACCOUNT_BLOB_URL"]
            credential = DefaultAzureCredential()
            cls._instance = BlobServiceClientAsync(account_url, credential=credential)
        return cls._instance

    @classmethod
    def get_storage_account_name(cls):
        account_url = os.environ["STORAGE_ACCOUNT_BLOB_URL"]
        return account_url.split("//")[1].split(".")[0]


def get_database_client(database_name: str) -> DatabaseProxy:
    client = CosmosClientSingleton.get_instance()
    return client.get_database_client(database_name)


def get_database_container_client(
    database_name: str, container_name: str
) -> ContainerProxy:
    db_client = get_database_client(database_name)
    return db_client.get_container_client(container_name)


class AzureStorageClientManager:
    """
    Manages the Azure storage clients for blob storage and Cosmos DB.

    Attributes:
        azure_storage_blob_url (str): The blob endpoint for azure storage.
        cosmos_uri_endpoint (str): The uri endpoint for the Cosmos DB.
        _blob_service_client (BlobServiceClient): The blob service client.
        _blob_service_client_async (BlobServiceClientAsync): The asynchronous blob service client.
        _cosmos_client (CosmosClient): The Cosmos DB client.
        _cosmos_database_client (DatabaseProxy): The Cosmos DB database client.
        _cosmos_container_client (ContainerProxy): The Cosmos DB container client.
    """

    def __init__(self) -> None:
        self._env = Env()
        self.azure_storage_blob_url = self._env.str(
            "STORAGE_ACCOUNT_BLOB_URL", ENDPOINT_ERROR_MSG
        )
        self.cosmos_uri_endpoint = self._env.str(
            "COSMOS_URI_ENDPOINT", ENDPOINT_ERROR_MSG
        )
        credential = DefaultAzureCredential()
        self._blob_service_client = BlobServiceClient(
            account_url=os.environ["STORAGE_ACCOUNT_BLOB_URL"], credential=credential
        )
        self._blob_service_client_async = BlobServiceClientAsync(
            account_url=os.environ["STORAGE_ACCOUNT_BLOB_URL"], credential=credential
        )
        self._cosmos_client = CosmosClient(
            url=os.environ["COSMOS_URI_ENDPOINT"], credential=credential
        )

    def get_blob_service_client(self) -> BlobServiceClient:
        """
        Returns the blob service client.

        Returns:
            BlobServiceClient: The blob service client.
        """
        return self._blob_service_client

    def get_blob_service_client_async(self) -> BlobServiceClientAsync:
        """
        Returns the asynchronous blob service client.

        Returns:
            BlobServiceClientAsync: The asynchronous blob service client.
        """
        return self._blob_service_client_async

    def get_cosmos_client(self) -> CosmosClient:
        """
        Returns the Cosmos DB client.

        Returns:
            CosmosClient: The Cosmos DB client.
        """
        return self._cosmos_client

    def get_cosmos_database_client(self, database_name: str) -> DatabaseProxy:
        """
        Returns the Cosmos DB database client.

        Args:
            database_name (str): The name of the database.

        Returns:
            DatabaseProxy: The Cosmos DB database client.
        """
        if not hasattr(self, "_cosmos_database_client"):
            self._cosmos_database_client = self._cosmos_client.get_database_client(
                database=database_name
            )
        return self._cosmos_database_client

    def get_cosmos_container_client(
        self, database_name: str, container_name: str
    ) -> ContainerProxy:
        """
        Returns the Cosmos DB container client.

        Args:
            database_name (str): The name of the database.
            container_name (str): The name of the container.

        Returns:
            ContainerProxy: The Cosmos DB container client.
        """
        if not hasattr(self, "_cosmos_container_client"):
            self._cosmos_container_client = self.get_cosmos_database_client(
                database_name=database_name
            ).get_container_client(container=container_name)
        return self._cosmos_container_client
