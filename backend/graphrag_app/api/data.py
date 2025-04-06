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
    status,
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
    subscription_key_check,
    update_cache,
)

data_route = APIRouter(
    prefix="/data",
    tags=["Data Management"],
)
if os.getenv("KUBERNETES_SERVICE_HOST"):
    data_route.dependencies.append(Depends(subscription_key_check))


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
                # extract text from file using MarkItDown
                md = MarkItDown()
                stream_info = StreamInfo(
                    extension=extension,
                )
                file_stream._file.seek(0)
                file_stream = file_stream._file
                result = md.convert_stream(
                    stream=file_stream,
                    stream_info=stream_info,
                )

                # remove illegal unicode characters and upload to blob storage
                cleaned_result = clean_output(result.text_content)
                await converted_blob_client.upload_blob(
                    cleaned_result, overwrite=overwrite
                )

                # update the file cache
                await update_cache(filename, file_stream, container_client)
        except Exception:
            # if any exception occurs, return the filename to indicate conversion/upload failures
            return upload_file.filename


def clean_output(val: str, replacement: str = ""):
    """Removes unicode characters that are invalid XML characters (not valid for graphml files at least)."""
    # fmt: off
    _illegal_xml_chars_RE = re.compile(
            "[\x00-\x08\x0b\x0c\x0e-\x1F\uD800-\uDFFF\uFFFE\uFFFF]"
        )
    # fmt: on
    return _illegal_xml_chars_RE.sub(replacement, val)


@data_route.post(
    "",
    summary="Upload data to a data storage container",
    response_model=BaseResponse,
    responses={status.HTTP_201_CREATED: {"model": BaseResponse}},
)
async def upload_files(
    files: List[UploadFile],
    container_name: str,
    sanitized_container_name: str = Depends(sanitize_name),
    overwrite: bool = True,
):
    """
    Create a Azure Storage container (if needed) and upload files. Multiple file types are supported, including pdf, powerpoint, word, excel, html, csv, json, xml, etc.
    The complete set of supported file types can be found in the MarkItDown (https://github.com/microsoft/markitdown) library.
    """
    try:
        # create the initial cache if it doesn't exist
        blob_container_client = await get_blob_container_client(
            sanitized_container_name
        )
        await create_cache(blob_container_client)

        # upload files in batches of 100 to avoid exceeding Azure Storage API limits
        processing_errors = []
        batch_size = 100
        num_batches = ceil(len(files) / batch_size)
        for i in range(num_batches):
            batch_files = files[i * batch_size : (i + 1) * batch_size]
            tasks = [
                upload_file_async(file, blob_container_client, overwrite)
                for file in batch_files
            ]
            results = await asyncio.gather(*tasks)
            results = [r for r in results if r is not None]
            processing_errors.extend(results)

        # update container-store entry in cosmosDB once upload process is successful
        cosmos_container_store_client = get_cosmos_container_store_client()
        cosmos_container_store_client.upsert_item({
            "id": sanitized_container_name,
            "human_readable_name": container_name,
            "type": "data",
        })

        if len(processing_errors) > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Error uploading files: {processing_errors}.",
            )
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
