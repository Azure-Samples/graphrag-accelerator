# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import inspect
import os
import traceback

import graphrag.api as api
import yaml
from fastapi import (
    APIRouter,
    HTTPException,
)
from graphrag.config.create_graphrag_config import create_graphrag_config

from src.api.azure_clients import AzureClientManager
from src.logger.load_logger import load_pipeline_logger
from src.utils.common import sanitize_name

prompt_tuning_route = APIRouter(prefix="/index/config", tags=["Index Configuration"])


@prompt_tuning_route.get(
    "/prompts",
    summary="Generate prompts from user-provided data.",
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

    # load pipeline configuration file (settings.yaml) for input data and other settings
    this_directory = os.path.dirname(
        os.path.abspath(inspect.getfile(inspect.currentframe()))
    )
    data = yaml.safe_load(open(f"{this_directory}/pipeline-settings.yaml"))
    data["input"]["container_name"] = sanitized_storage_name
    graphrag_config = create_graphrag_config(values=data, root_dir=".")

    # generate prompts
    try:
        # NOTE: we need to call api.generate_indexing_prompts
        prompts: tuple[str, str, str] = await api.generate_indexing_prompts(
            config=graphrag_config,
            root=".",
            limit=limit,
            selection_method="random",
        )
    except Exception as e:
        logger = load_pipeline_logger()
        error_details = {
            "storage_name": storage_name,
        }
        logger.error(
            message="Auto-prompt generation failed.",
            cause=e,
            stack=traceback.format_exc(),
            details=error_details,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error generating prompts for data in '{storage_name}'. Please try a lower limit.",
        )

    content = {
        "entity_extraction_prompt": prompts[0],
        "entity_summarization_prompt": prompts[1],
        "community_summarization_prompt": prompts[2],
    }
    return content  # return a fastapi.responses.JSONResponse object
