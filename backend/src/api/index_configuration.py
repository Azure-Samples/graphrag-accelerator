# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import inspect
import os
import shutil
import traceback

import yaml
from fastapi import (
    APIRouter,
    HTTPException,
)
from fastapi.responses import StreamingResponse
from graphrag.prompt_tune.cli import prompt_tune as generate_fine_tune_prompts

from src.api.azure_clients import AzureClientManager
from src.api.common import (
    sanitize_name,
)
from src.logger import LoggerSingleton

index_configuration_route = APIRouter(
    prefix="/index/config", tags=["Index Configuration"]
)


@index_configuration_route.get(
    "/prompts",
    summary="Generate graphrag prompts from user-provided data.",
    description="Generating custom prompts from user-provided data may take several minutes to run based on the amount of data used.",
)
async def generate_prompts(storage_name: str, limit: int = 5):
    """
    Automatically generate custom prompts for entity entraction,
    community reports, and summarize descriptions based on a sample of provided data.
    """
    # check for storage container existence
    azure_client_manager = AzureClientManager()
    blob_service_client = azure_client_manager.get_blob_service_client()
    sanitized_storage_name = sanitize_name(storage_name)
    if not blob_service_client.get_container_client(sanitized_storage_name).exists():
        raise HTTPException(
            status_code=500,
            detail=f"Data container '{storage_name}' does not exist.",
        )
    this_directory = os.path.dirname(
        os.path.abspath(inspect.getfile(inspect.currentframe()))
    )

    # write custom settings.yaml to a file and store in a temporary directory
    data = yaml.safe_load(open(f"{this_directory}/pipeline-settings.yaml"))
    data["input"]["container_name"] = sanitized_storage_name
    temp_dir = f"/tmp/{sanitized_storage_name}_prompt_tuning"
    shutil.rmtree(temp_dir, ignore_errors=True)
    os.makedirs(temp_dir, exist_ok=True)
    with open(f"{temp_dir}/settings.yaml", "w") as f:
        yaml.dump(data, f, default_flow_style=False)

    # generate prompts
    try:
        await generate_fine_tune_prompts(
            config=f"{temp_dir}/settings.yaml",
            root=temp_dir,
            domain="",
            selection_method="random",
            limit=limit,
            skip_entity_types=True,
            output=f"{temp_dir}/prompts",
        )
    except Exception as e:
        logger = LoggerSingleton().get_instance()
        error_details = {
            "storage_name": storage_name,
        }
        logger.on_error(
            message="Auto-prompt generation failed.",
            cause=e,
            stack=traceback.format_exc(),
            details=error_details,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error generating prompts for data in '{storage_name}'. Please try a lower limit.",
        )

    # zip up the generated prompt files and return the zip file
    temp_archive = (
        f"{temp_dir}/prompts"  # will become a zip file with the name prompts.zip
    )
    shutil.make_archive(temp_archive, "zip", root_dir=temp_dir, base_dir="prompts")

    def iterfile(file_path: str):
        with open(file_path, mode="rb") as file_like:
            yield from file_like

    return StreamingResponse(iterfile(f"{temp_archive}.zip"))
