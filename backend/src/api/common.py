# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import hashlib
import re

from fastapi import HTTPException

from src.api.azure_clients import (
    AzureClientManager,
    BlobServiceClientSingleton,
)

blob_service_client = BlobServiceClientSingleton.get_instance()
azure_storage_client_manager = AzureClientManager()


def delete_blob_container(container_name: str):
    """
    Delete a blob container. If it does not exist, do nothing.
    If exception is raised, the calling function should catch it.
    """
    if blob_service_client.get_container_client(container_name).exists():
        blob_service_client.delete_container(container_name)


def validate_index_file_exist(index_name: str, file_name: str):
    """
    Check if index exists and that the specified blob file exists.

    A "valid" index is defined by having an entry in the container-store table in cosmos db.
    Further checks are done to ensure the blob container and file exist.

    Args:
    -----
    index_name (str)
        Name of the index to validate.
    file_name (str)
        The blob file to be validated.

    Raises: ValueError
    """
    # verify index_name is a valid index by checking container-store in cosmos db
    try:
        container_store_client = (
            azure_storage_client_manager.get_cosmos_container_client(
                database_name="graphrag", container_name="container-store"
            )
        )
        container_store_client.read_item(index_name, index_name)
    except Exception:
        raise ValueError(f"Container {index_name} is not a valid index.")
    # check for file existence
    index_container_client = blob_service_client.get_container_client(index_name)
    if not index_container_client.exists():
        raise ValueError(f"Container {index_name} not found.")
    if not index_container_client.get_blob_client(file_name).exists():
        raise ValueError(f"File {file_name} in container {index_name} not found.")


def validate_blob_container_name(container_name: str):
    """
    Check if container name is valid based on Azure resource naming rules.

        - A blob container name must be between 3 and 63 characters in length.
        - Start with a letter or number
        - All letters used in blob container names must be lowercase.
        - Contain only letters, numbers, or the hyphen.
        - Consecutive hyphens are not permitted.
        - Cannot end with a hyphen.

    Args:
    -----
    container_name (str)
        The blob container name to be validated.

    Raises: ValueError
    """
    # Check the length of the name
    if len(container_name) < 3 or len(container_name) > 63:
        raise ValueError(
            f"Container name must be between 3 and 63 characters in length. Name provided was {len(container_name)} characters long."
        )

    # Check if the name starts with a letter or number
    if not container_name[0].isalnum():
        raise ValueError(
            f"Container name must start with a letter or number. Starting character was {container_name[0]}."
        )

    # Check for valid characters (letters, numbers, hyphen) and lowercase letters
    if not re.match("^[a-z0-9-]+$", container_name):
        raise ValueError(
            f"Container name must only contain:\n- lowercase letters\n- numbers\n- or hyphens\nName provided was {container_name}."
        )

    # Check for consecutive hyphens
    if "--" in container_name:
        raise ValueError(
            f"Container name cannot contain consecutive hyphens. Name provided was {container_name}."
        )

    # Check for hyphens at the end of the name
    if container_name[-1] == "-":
        raise ValueError(
            f"Container name cannot end with a hyphen. Name provided was {container_name}."
        )


def sanitize_name(name: str | None) -> str | None:
    """
    Sanitize a human-readable name by converting it to a SHA256 hash, then truncate
    to 128 bit length to ensure it is within the 63 character limit imposed by Azure Storage.

    The sanitized name will be used to identify container names in both Azure Storage and CosmosDB.

    Args:
    -----
    name (str)
        The name to be sanitized.

    Returns: str
        The sanitized name.
    """
    if not name:
        return None
    name = name.encode()
    name_hash = hashlib.sha256(name)
    truncated_hash = name_hash.digest()[:16]  # get the first 16 bytes (128 bits)
    return truncated_hash.hex()


def retrieve_original_blob_container_name(sanitized_name: str) -> str | None:
    """
    Retrieve the original human-readable container name of a sanitized blob name.

    Args:
    -----
    sanitized_name (str)
        The sanitized name to be converted back to the original name.

    Returns: str
        The original human-readable name.
    """
    try:
        container_store_client = (
            azure_storage_client_manager.get_cosmos_container_client(
                database_name="graphrag", container_name="container-store"
            )
        )
        for item in container_store_client.read_all_items():
            if item["id"] == sanitized_name:
                return item["human_readable_name"]
    except Exception:
        raise HTTPException(
            status_code=500, detail="Error retrieving original blob name."
        )
    return None


def retrieve_original_entity_config_name(sanitized_name: str) -> str | None:
    """
    Retrieve the original human-readable entity config name of a sanitized entity config name.

    Args:
    -----
    sanitized_name (str)
        The sanitized name to be converted back to the original name.

    Returns: str
        The original human-readable name.
    """
    try:
        container_store_client = (
            azure_storage_client_manager.get_cosmos_container_client(
                database_name="graphrag", container_name="entities"
            )
        )
        for item in container_store_client.read_all_items():
            if item["id"] == sanitized_name:
                return item["human_readable_name"]
    except Exception:
        raise HTTPException(
            status_code=500, detail="Error retrieving original entity config name."
        )
    return None
