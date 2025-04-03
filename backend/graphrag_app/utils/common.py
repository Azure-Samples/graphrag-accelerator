# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import csv
import hashlib
import os
import traceback
from hashlib import sha256
from io import StringIO
from typing import BinaryIO
from typing import Annotated

import pandas as pd
from azure.core.exceptions import ResourceNotFoundError
from azure.cosmos import ContainerProxy, exceptions
from azure.identity import DefaultAzureCredential
from azure.storage.blob.aio import ContainerClient
from fastapi import Header, HTTPException

from graphrag_app.logger.load_logger import load_pipeline_logger
from graphrag_app.utils.azure_clients import AzureClientManager


def get_df(
    table_path: str,
) -> pd.DataFrame:
    df = pd.read_parquet(
        table_path,
        storage_options=pandas_storage_options(),
    )
    return df


def pandas_storage_options() -> dict:
    """Generate the storage options required by pandas to read parquet files from Storage."""
    # For more information on the options available, see: https://github.com/fsspec/adlfs?tab=readme-ov-file#setting-credentials
    azure_client_manager = AzureClientManager()
    options = {
        "account_name": azure_client_manager.storage_account_name,
        "account_host": azure_client_manager.storage_account_hostname,
    }
    if os.getenv("STORAGE_CONNECTION_STRING"):
        options["connection_string"] = os.getenv("STORAGE_CONNECTION_STRING")
    else:
        options["credential"] = DefaultAzureCredential()
    return options


def delete_storage_container_if_exist(container_name: str):
    """
    Delete a blob container. If it does not exist, do nothing.
    If exception is raised, the calling function should catch it.
    """
    azure_client_manager = AzureClientManager()
    blob_service_client = azure_client_manager.get_blob_service_client()
    try:
        blob_service_client.delete_container(container_name)
    except ResourceNotFoundError:
        # do nothing if container does not exist
        pass


def delete_cosmos_container_item_if_exist(container: str, item_id: str):
    """
    Delete an item from a cosmosdb container. If it does not exist, do nothing.
    If exception is raised, the calling function should catch it.
    """
    azure_client_manager = AzureClientManager()
    try:
        azure_client_manager.get_cosmos_container_client(
            database="graphrag", container=container
        ).delete_item(item_id, item_id)
    except ResourceNotFoundError:
        # do nothing if item does not exist
        pass


def validate_index_file_exist(sanitized_container_name: str, file_name: str):
    """
    Check if index exists and that the specified blob file exists.

    A "valid" index is defined by having an entry in the container-store table in cosmos db.
    Further checks are done to ensure the blob container and file exist.

    Args:
    -----
    sanitized_container_name (str)
        Sanitized name of a blob container.
    file_name (str)
        The blob file to be validated.

    Raises: ValueError
    """
    azure_client_manager = AzureClientManager()
    original_container_name = desanitize_name(sanitized_container_name)
    try:
        cosmos_container_client = get_cosmos_container_store_client()
        cosmos_container_client.read_item(
            sanitized_container_name, sanitized_container_name
        )
    except Exception:
        raise ValueError(f"{original_container_name} is not a valid index.")
    # check for file existence
    index_container_client = (
        azure_client_manager.get_blob_service_client().get_container_client(
            sanitized_container_name
        )
    )
    if not index_container_client.exists():
        raise ValueError(f"{original_container_name} not found.")
    if not index_container_client.get_blob_client(file_name).exists():
        raise ValueError(
            f"File {file_name} unavailable for container {original_container_name}."
        )


def get_cosmos_container_store_client() -> ContainerProxy:
    try:
        azure_client_manager = AzureClientManager()
        return azure_client_manager.get_cosmos_container_client(
            database="graphrag", container="container-store"
        )
    except Exception as e:
        logger = load_pipeline_logger()
        logger.error(
            message="Error fetching cosmosdb client.",
            cause=e,
            stack=traceback.format_exc(),
        )
        raise HTTPException(status_code=500, detail="Error fetching cosmosdb client.")


async def get_blob_container_client(name: str) -> ContainerClient:
    try:
        azure_client_manager = AzureClientManager()
        blob_service_client = azure_client_manager.get_blob_service_client_async()
        container_client = blob_service_client.get_container_client(name)
        if not await container_client.exists():
            await container_client.create_container()
        return container_client
    except Exception as e:
        logger = load_pipeline_logger()
        logger.error(
            message="Error fetching storage client.",
            cause=e,
            stack=traceback.format_exc(),
        )
        raise HTTPException(status_code=500, detail="Error fetching storage client.")


def sanitize_name(container_name: str) -> str:
    """
    Sanitize a user-provided string to be used as an Azure Storage container name.
    Convert the string to a SHA256 hash, then truncate to 128 bit length to ensure
    it is within the 63 character limit imposed by Azure Storage.

    The sanitized name will be used to identify container names in both Azure Storage and CosmosDB.

    Args:
    -----
    name (str)
        The name to be sanitized.

    Returns: str
        The sanitized name.
    """
    container_name = container_name.encode()
    hashed_name = hashlib.sha256(container_name)
    truncated_hash = hashed_name.digest()[:16]  # get the first 16 bytes (128 bits)
    return truncated_hash.hex()


def desanitize_name(sanitized_container_name: str) -> str | None:
    """
    Reverse the sanitization process by retrieving the original user-provided name.

    Args:
    -----
    sanitized_name (str)
        The sanitized name to be converted back to the original name.

    Returns: str | None
        The original human-readable name or None if it does not exist.
    """
    try:
        container_store_client = get_cosmos_container_store_client()
        try:
            return container_store_client.read_item(
                sanitized_container_name, sanitized_container_name
            )["human_readable_name"]
        except exceptions.CosmosResourceNotFoundError:
            return None
    except Exception:
        raise HTTPException(
            status_code=500, detail="Error retrieving original container name."
        )


async def subscription_key_check(
    Ocp_Apim_Subscription_Key: Annotated[str, Header()],
):
    """
    Verifies if user has passed the Ocp_Apim_Subscription_Key (APIM subscription key) in the request header.
    If it is not present, an HTTPException with a 400 status code is raised.
    Note: this check is unnecessary (APIM validates subscription keys automatically), but this will add the key
    as a required parameter in the swagger docs page, enabling users to send requests using the swagger docs "Try it out" feature.
    """
    if not Ocp_Apim_Subscription_Key:
        raise HTTPException(
            status_code=400, detail="Ocp-Apim-Subscription-Key required"
        )
    return Ocp_Apim_Subscription_Key


async def create_cache(container_client: ContainerClient) -> None:
    """
    Create a file cache to track the uploaded files if it doesn't exist.
    """
    try:
        cache_blob_client = container_client.get_blob_client("uploaded_files_cache.csv")
        if not await cache_blob_client.exists():
            # create the empty file cache csv
            headers = [["Filename", "Hash"]]
            with open("uploaded_files_cache.csv", "w", newline="") as f:
                writer = csv.writer(f, delimiter=",")
                writer.writerows(headers)

            # upload to Azure Blob Storage and remove the temporary file
            with open("uploaded_files_cache.csv", "rb") as f:
                await cache_blob_client.upload_blob(f, overwrite=True)
            if os.path.exists("uploaded_files_cache.csv"):
                os.remove("uploaded_files_cache.csv")
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Error creating file cache in Azure Blob Storage.",
        )


async def check_cache(file_stream: BinaryIO, container_client: ContainerClient) -> bool:
    """
    Check if the file has already been uploaded.
    """
    try:
        # load the file cache
        cache_blob_client = container_client.get_blob_client("uploaded_files_cache.csv")
        cache_download_stream = await cache_blob_client.download_blob()
        cache_bytes = await cache_download_stream.readall()
        cache_content = StringIO(cache_bytes.decode("utf-8"))

        # comupte the sha256 hash of the file and check if it exists in the cache
        cache_reader = csv.reader(cache_content, delimiter=",")
        file_hash = sha256(file_stream.read()).hexdigest()
        for row in cache_reader:
            if file_hash in row:
                return True
        return False
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Error checking file cache in Azure Blob Storage.",
        )


async def update_cache(
    filename: str, file_stream: BinaryIO, container_client: ContainerClient
) -> None:
    """
    Update the file cache with the new file by appending a new row to the cache.
    """
    try:
        # Load the file cache
        cache_blob_client = container_client.get_blob_client("uploaded_files_cache.csv")
        cache_download_stream = await cache_blob_client.download_blob()
        cache_bytes = await cache_download_stream.readall()
        cache_content = StringIO(cache_bytes.decode("utf-8"))

        # Read existing rows and prepare to append
        cache_reader = csv.reader(cache_content, delimiter=",")
        existing_rows = list(cache_reader)

        # Compute the sha256 hash of the file and append it to the cache
        file_hash = sha256(file_stream.read()).hexdigest()
        new_row = [filename, file_hash]
        existing_rows.append(new_row)

        # Write the updated content back to the StringIO object
        updated_cache_content = StringIO()
        cache_writer = csv.writer(updated_cache_content, delimiter=",")
        cache_writer.writerows(existing_rows)

        # Upload the updated cache to Azure Blob Storage
        updated_cache_content.seek(0)
        await cache_blob_client.upload_blob(
            updated_cache_content.getvalue().encode("utf-8"), overwrite=True
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Error updating file cache in Azure Blob Storage.",
        )
