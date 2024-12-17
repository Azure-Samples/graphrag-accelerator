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


class CosmosClientSingleton:
    """
    Singleton class for a CosmosClient instance.

    If a connection string is available, it will be used to create the CosmosClient instance.
    Otherwise assume managed identity is used.
    """

    _instance = None

    @classmethod
    def get_instance(cls):
        if not cls._instance:
            endpoint = os.getenv("COSMOS_URI_ENDPOINT")
            conn_string = os.getenv("COSMOS_CONNECTION_STRING")
            if conn_string:
                cls._instance = CosmosClient.from_connection_string(conn_string)
            else:
                credential = DefaultAzureCredential()
                cls._instance = CosmosClient(endpoint, credential)
        return cls._instance


class BlobServiceClientSingleton:
    """
    Singleton class for BlobServiceClient.

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

    @classmethod
    def get_storage_account_name(cls) -> str:
        conn_string = os.getenv("STORAGE_CONNECTION_STRING")
        if conn_string:
            # parse account name from the connection string
            meta_info = {}
            for meta_data in conn_string.split(";"):
                if not meta_data:
                    continue
                m = meta_data.split("=", 1)
                if len(m) != 2:
                    continue
                meta_info[m[0]] = m[1]
            return meta_info["AccountName"]
        else:
            account_url = os.getenv("STORAGE_ACCOUNT_BLOB_URL")
            return account_url.split("//")[1].split(".")[0]


class BlobServiceClientSingletonAsync:
    _instance = None
    _env = Env()

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

    @classmethod
    def get_storage_account_name(cls) -> str:
        conn_string = os.getenv("STORAGE_CONNECTION_STRING")
        if conn_string:
            # parse account name from the connection string
            meta_info = {}
            for meta_data in conn_string.split(";"):
                if not meta_data:
                    continue
                m = meta_data.split("=", 1)
                if len(m) != 2:
                    continue
                meta_info[m[0]] = m[1]
            return meta_info["AccountName"]
        else:
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


class AzureClientManager:
    """
    Manages the clients for Azure blob storage and Cosmos DB.

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
        self.azure_storage_blob_url = os.getenv("STORAGE_ACCOUNT_BLOB_URL")
        self.azure_storage_connection_string = os.getenv("STORAGE_CONNECTION_STRING")
        self.cosmos_uri_endpoint = os.getenv("COSMOS_URI_ENDPOINT")
        self.cosmos_connection_string = os.getenv("COSMOS_CONNECTION_STRING")

        if self.cosmos_connection_string:
            self._cosmos_client = CosmosClient.from_connection_string(
                self.cosmos_connection_string
            )
        else:
            self._cosmos_client = CosmosClient(
                self.cosmos_uri_endpoint, credential=DefaultAzureCredential()
            )
        if self.azure_storage_connection_string:
            self._blob_service_client = BlobServiceClient.from_connection_string(
                self.azure_storage_connection_string
            )
            self._blob_service_client_async = (
                BlobServiceClientAsync.from_connection_string(
                    self.azure_storage_connection_string
                )
            )
        else:
            self._blob_service_client = BlobServiceClient(
                account_url=self.azure_storage_blob_url,
                credential=DefaultAzureCredential(),
            )
            self._blob_service_client_async = BlobServiceClientAsync(
                account_url=self.azure_storage_blob_url,
                credential=DefaultAzureCredential(),
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
        if not hasattr(self, "_cosmos_database_client"):
            self._cosmos_database_client = self._cosmos_client.get_database_client(
                database=database_name
            )
        return self._cosmos_database_client

    def get_cosmos_container_client(
        self, database_name: str, container_name: str
    ) -> ContainerProxy:
        """
        Returns a Cosmos container client.

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
