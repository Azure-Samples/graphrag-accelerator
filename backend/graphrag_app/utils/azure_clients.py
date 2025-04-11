# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
from pathlib import PurePosixPath

from azure.cosmos import (
    ContainerProxy,
    CosmosClient,
    DatabaseProxy,
)
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from azure.storage.blob.aio import BlobServiceClient as BlobServiceClientAsync

ENDPOINT_ERROR_MSG = "Could not find connection string in environment variables"


class _CosmosClientSingleton:
    """
    Singleton class for a CosmosClient instance.

    If a connection string is available, it will be used to create the CosmosClient instance.
    Otherwise assume managed identity is used.
    """

    _instance = None

    @classmethod
    def get_instance(cls):
        if not cls._instance:
            conn_string = os.getenv("COSMOS_CONNECTION_STRING")
            if conn_string:
                cls._instance = CosmosClient.from_connection_string(conn_string)
            else:
                endpoint = os.getenv("COSMOS_URI_ENDPOINT")
                credential = DefaultAzureCredential()
                cls._instance = CosmosClient(endpoint, credential)
        return cls._instance


class _BlobServiceClientSingleton:
    """
    Singleton class for a BlobServiceClient instance.

    If a connection string is available, it will be used to create the BlobServiceClient instance.
    Otherwise assume managed identity is used.
    """

    _instance = None

    @classmethod
    def get_instance(cls) -> BlobServiceClient:
        if cls._instance is None:
            conn_string = os.getenv("STORAGE_CONNECTION_STRING")
            if conn_string:
                cls._instance = BlobServiceClient.from_connection_string(conn_string)
            else:
                account_url = os.getenv("STORAGE_ACCOUNT_BLOB_URL")
                credential = DefaultAzureCredential()
                cls._instance = BlobServiceClient(account_url, credential=credential)
        return cls._instance


class _BlobServiceClientSingletonAsync:
    """
    Singleton class for a BlobServiceClientAsync instance.

    If a connection string is available, it will be used to create the BlobServiceClientAsync instance.
    Otherwise assume managed identity is used.
    """

    _instance = None

    @classmethod
    def get_instance(cls) -> BlobServiceClientAsync:
        if cls._instance is None:
            conn_string = os.getenv("STORAGE_CONNECTION_STRING")
            if conn_string:
                cls._instance = BlobServiceClientAsync.from_connection_string(
                    conn_string
                )
            else:
                account_url = os.environ["STORAGE_ACCOUNT_BLOB_URL"]
                credential = DefaultAzureCredential()
                cls._instance = BlobServiceClientAsync(
                    account_url, credential=credential
                )
        return cls._instance


class AzureClientManager:
    """
    Manages the clients for Azure blob storage and Cosmos DB.

    Attributes:
        storage_blob_url (str): The blob endpoint for azure storage.
        storage_account_name (str): The name of the azure storage account.
        storage_account_hostname (str): The hostname of the azure blob storage account.
        cosmos_uri_endpoint (str): The uri endpoint for the Cosmos DB.
        _blob_service_client (BlobServiceClient): The blob service client.
        _blob_service_client_async (BlobServiceClientAsync): The asynchronous blob service client.
        _cosmos_client (CosmosClient): The Cosmos DB client.
        _cosmos_database_client (DatabaseProxy): The Cosmos DB database client.
        _cosmos_container_client (ContainerProxy): The Cosmos DB container client.
    """

    def __init__(self) -> None:
        self.storage_blob_url = os.getenv("STORAGE_ACCOUNT_BLOB_URL")
        self.storage_connection_string = os.getenv("STORAGE_CONNECTION_STRING")
        self.cosmos_uri_endpoint = os.getenv("COSMOS_URI_ENDPOINT")
        self.cosmos_connection_string = os.getenv("COSMOS_CONNECTION_STRING")
        self._cosmos_client = _CosmosClientSingleton.get_instance()
        self._blob_service_client = _BlobServiceClientSingleton.get_instance()
        self._blob_service_client_async = (
            _BlobServiceClientSingletonAsync.get_instance()
        )

        # parse account hostname from the azure storage connection string or blob url
        self.storage_account_hostname = PurePosixPath(self.storage_blob_url).parts[1]
        
        # parse account name from the azure storage connection string or blob url
        if self.storage_connection_string:
            meta_info = {}
            for meta_data in self.storage_connection_string.split(";"):
                if not meta_data:
                    continue
                m = meta_data.split("=", 1)
                if len(m) != 2:
                    continue
                meta_info[m[0]] = m[1]
            self.storage_account_name = meta_info["AccountName"]
        else:
            self.storage_account_name = self.storage_account_hostname.split(".")[0]

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
        Returns a Cosmos client.

        Returns:
            CosmosClient: The Cosmos DB client.
        """
        return self._cosmos_client

    def get_cosmos_database_client(self, database_name: str) -> DatabaseProxy:
        """
        Returns a Cosmos database client.

        Args:
            database_name (str): The name of the database.

        Returns:
            DatabaseProxy: The Cosmos database client.
        """
        return self._cosmos_client.get_database_client(database=database_name)

    def get_cosmos_container_client(
        self, database: str, container: str
    ) -> ContainerProxy:
        """
        Returns a Cosmos container client.

        Args:
            database_name (str): The name of the database.
            container_name (str): The name of the container.

        Returns:
            ContainerProxy: The Cosmos DB container client.
        """
        return self._cosmos_client.get_database_client(
            database=database
        ).get_container_client(container=container)
