# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import asyncio
import re
from math import ceil
from typing import List

from azure.storage.blob import ContainerClient
from fastapi import (
    APIRouter,
    HTTPException,
    UploadFile,
)

from src.api.azure_clients import AzureClientManager
from src.api.common import (
    delete_blob_container,
    delete_cosmos_container_item,
    sanitize_name,
    validate_blob_container_name,
)
from src.logger import LoggerSingleton
from src.models import (
    BaseResponse,
    StorageNameList,
)

data_route = APIRouter(
    prefix="/data",
    tags=["Data Management"],
)


@data_route.get(
    "",
    summary="Get all data storage containers.",
    response_model=StorageNameList,
    responses={200: {"model": StorageNameList}},
)
async def get_all_data_storage_containers():
    """
    Retrieve a list of all data storage containers.
    """
    azure_client_manager = AzureClientManager()
    items = []
    try:
        container_store_client = azure_client_manager.get_cosmos_container_client(
            database="graphrag", container="container-store"
        )
        for item in container_store_client.read_all_items():
            if item["type"] == "data":
                items.append(item["human_readable_name"])
    except Exception:
        reporter = LoggerSingleton().get_instance()
        reporter.on_error("Error getting list of blob containers.")
        raise HTTPException(
            status_code=500, detail="Error getting list of blob containers."
        )
    return StorageNameList(storage_name=items)


async def upload_file_async(
    upload_file: UploadFile, container_client: ContainerClient, overwrite: bool = True
) -> None:
    """
    Asynchronously upload a file to the specified blob container.
    Silently ignore errors that occur when overwrite=False.
    """
    blob_client = container_client.get_blob_client(upload_file.filename)
    with upload_file.file as file_stream:
        try:
            await blob_client.upload_blob(file_stream, overwrite=overwrite)
        except Exception:
            pass


class Cleaner:
    def __init__(self, file):
        self.file = file
        self.name = file.name
        self.changes = 0

    def clean(self, val, replacement=""):
        # fmt: off
        _illegal_xml_chars_RE = re.compile(
            "[\x00-\x08\x0b\x0c\x0e-\x1F\uD800-\uDFFF\uFFFE\uFFFF]"
        )
        # fmt: on
        self.changes += len(_illegal_xml_chars_RE.findall(val))
        return _illegal_xml_chars_RE.sub(replacement, val)

    def read(self, n):
        return self.clean(self.file.read(n).decode()).encode(
            encoding="utf-8", errors="strict"
        )

    def name(self):
        return self.file.name

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.file.close()


@data_route.post(
    "",
    summary="Upload data to a data storage container",
    response_model=BaseResponse,
    responses={200: {"model": BaseResponse}},
)
async def upload_files(
    files: List[UploadFile], storage_name: str, overwrite: bool = True
):
    """
    Create a data storage container in Azure and upload files to it.

    Args:
        files (List[UploadFile]): A list of files to be uploaded.
        storage_name (str): The name of the Azure Blob Storage container to which files will be uploaded.
        overwrite (bool): Whether to overwrite existing files with the same name. Defaults to True. If False, files that already exist will be skipped.

    Returns:
        BaseResponse: An instance of the BaseResponse model with a status message indicating the result of the upload.

    Raises:
        HTTPException: If the container name is invalid or if any error occurs during the upload process.
    """
    sanitized_storage_name = sanitize_name(storage_name)
    # ensure container name follows Azure Blob Storage naming conventions
    try:
        validate_blob_container_name(sanitized_storage_name)
    except ValueError:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid blob container name: '{storage_name}'. Please try a different name.",
        )
    try:
        azure_client_manager = AzureClientManager()
        blob_service_client = azure_client_manager.get_blob_service_client_async()
        container_client = blob_service_client.get_container_client(
            sanitized_storage_name
        )
        if not await container_client.exists():
            await container_client.create_container()

        # clean files - remove illegal XML characters
        files = [UploadFile(Cleaner(f.file), filename=f.filename) for f in files]

        # upload files in batches of 1000 to avoid exceeding Azure Storage API limits
        batch_size = 1000
        batches = ceil(len(files) / batch_size)
        for i in range(batches):
            batch_files = files[i * batch_size : (i + 1) * batch_size]
            tasks = [
                upload_file_async(file, container_client, overwrite)
                for file in batch_files
            ]
            await asyncio.gather(*tasks)
        # update container-store in cosmosDB since upload process was successful
        container_store_client = azure_client_manager.get_cosmos_container_client(
            database="graphrag", container="container-store"
        )
        container_store_client.upsert_item({
            "id": sanitized_storage_name,
            "human_readable_name": storage_name,
            "type": "data",
        })
        return BaseResponse(status="File upload successful.")
    except Exception:
        logger = LoggerSingleton().get_instance()
        logger.on_error("Error uploading files.", details={"files": files})
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading files to container '{storage_name}'.",
        )


@data_route.delete(
    "/{storage_name}",
    summary="Delete a data storage container",
    response_model=BaseResponse,
    responses={200: {"model": BaseResponse}},
)
async def delete_files(storage_name: str):
    """
    Delete a specified data storage container.
    """
    # azure_client_manager = AzureClientManager()
    sanitized_storage_name = sanitize_name(storage_name)
    try:
        # delete container in Azure Storage
        delete_blob_container(sanitized_storage_name)
        # delete entry from container-store in cosmosDB
        delete_cosmos_container_item("container-store", sanitized_storage_name)
    except Exception:
        logger = LoggerSingleton().get_instance()
        logger.on_error(
            f"Error deleting container {storage_name}.",
            details={"Container": storage_name},
        )
        raise HTTPException(
            status_code=500, detail=f"Error deleting container '{storage_name}'."
        )
    return BaseResponse(status="Success")
