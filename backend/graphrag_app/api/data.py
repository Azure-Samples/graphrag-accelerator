# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import asyncio
import os
import re
import traceback
from math import ceil
from typing import List

from azure.storage.blob.aio import ContainerClient
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
)
from markitdown import MarkItDown, StreamInfo

from graphrag_app.logger.load_logger import load_pipeline_logger
from graphrag_app.typing.models import (
    BaseResponse,
    StorageNameList,
)
from graphrag_app.utils.common import (
    check_cache,
    create_cache,
    delete_cosmos_container_item_if_exist,
    delete_storage_container_if_exist,
    get_blob_container_client,
    get_cosmos_container_store_client,
    sanitize_name,
    update_cache,
)

data_route = APIRouter(
    prefix="/data",
    tags=["Data Management"],
)


@data_route.get(
    "",
    summary="Get list of data containers.",
    response_model=StorageNameList,
    responses={200: {"model": StorageNameList}},
)
async def get_all_data_containers():
    """
    Retrieve a list of all data containers.
    """
    items = []
    try:
        container_store_client = get_cosmos_container_store_client()
        for item in container_store_client.read_all_items():
            if item["type"] == "data":
                items.append(item["human_readable_name"])
    except Exception as e:
        reporter = load_pipeline_logger()
        reporter.error(
            message="Error getting list of blob containers.",
            cause=e,
            stack=traceback.format_exc(),
        )
        raise HTTPException(
            status_code=500, detail="Error getting list of blob containers."
        )
    return StorageNameList(storage_name=items)


async def upload_file_async(
    upload_file: UploadFile, container_client: ContainerClient, overwrite: bool = True
) -> None:
    """
    Asynchronously convert and upload a file to the specified blob container.
    Silently ignore errors that occur when overwrite=False.
    """
    filename = upload_file.filename
    extension = os.path.splitext(filename)[1]
    converted_filename = filename.replace(extension, ".txt")
    converted_blob_client = container_client.get_blob_client(converted_filename)

    with upload_file.file as file_stream:
        try:
            if not await check_cache(file_stream, container_client):
                # extract text from file and upload to Azure Blob Storage
                md = MarkItDown()
                stream_info = StreamInfo(
                    extension=extension,
                )
                file_stream.file._file.seek(0)
                file_stream = file_stream.file._file
                result = md.convert_stream(
                    stream=file_stream,
                    stream_info=stream_info,
                )
                await converted_blob_client.upload_blob(result.text_content, overwrite=overwrite)

                # update the file cache
                await update_cache(filename, file_stream, container_client)
        except Exception:
            raise HTTPException(
                status_code=500,
                detail=f"Error uploading file '{filename}' to container '{container_client.container_name}'.",
            )


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

    def read(self, n: int = -1):
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
    files: List[UploadFile],
    container_name: str,
    sanitized_container_name: str = Depends(sanitize_name),
    overwrite: bool = True,
):
    """
    Create a Azure Storage container and upload files to it.

    Args:
        files (List[UploadFile]): A list of files to be uploaded.
        storage_name (str): The name of the Azure Blob Storage container to which files will be uploaded.
        overwrite (bool): Whether to overwrite existing files with the same name. Defaults to True. If False, files that already exist will be skipped.

    Returns:
        BaseResponse: An instance of the BaseResponse model with a status message indicating the result of the upload.

    Raises:
        HTTPException: If the container name is invalid or if any error occurs during the upload process.
    """
    try:
        # clean files - remove illegal XML characters
        files = [UploadFile(Cleaner(f.file), filename=f.filename) for f in files]

        blob_container_client = await get_blob_container_client(
            sanitized_container_name
        )

        await create_cache(blob_container_client)

        # upload files in batches of 1000 to avoid exceeding Azure Storage API limits
        batch_size = 1000
        num_batches = ceil(len(files) / batch_size)
        for i in range(num_batches):
            batch_files = files[i * batch_size : (i + 1) * batch_size]
            tasks = [
                upload_file_async(file, blob_container_client, overwrite)
                for file in batch_files
            ]
            await asyncio.gather(*tasks)

        # update container-store entry in cosmosDB once upload process is successful
        cosmos_container_store_client = get_cosmos_container_store_client()
        cosmos_container_store_client.upsert_item({
            "id": sanitized_container_name,
            "human_readable_name": container_name,
            "type": "data",
        })
        return BaseResponse(status="File upload successful.")
    except Exception as e:
        logger = load_pipeline_logger()
        logger.error(
            message="Error uploading files.",
            cause=e,
            stack=traceback.format_exc(),
            details={"files": [f.filename for f in files]},
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading files to container '{container_name}'.",
        )


@data_route.delete(
    "/{container_name}",
    summary="Delete a data storage container",
    response_model=BaseResponse,
    responses={200: {"model": BaseResponse}},
)
async def delete_files(
    container_name: str, sanitized_container_name: str = Depends(sanitize_name)
):
    """
    Delete a specified data storage container.
    """
    try:
        delete_storage_container_if_exist(sanitized_container_name)
        delete_cosmos_container_item_if_exist(
            "container-store", sanitized_container_name
        )
    except Exception as e:
        logger = load_pipeline_logger()
        logger.error(
            message=f"Error deleting container {container_name}.",
            cause=e,
            stack=traceback.format_exc(),
            details={"Container": container_name},
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting container '{container_name}'.",
        )
    return BaseResponse(status="Success")
