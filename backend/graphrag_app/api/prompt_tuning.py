# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import traceback
from pathlib import Path

import graphrag.api as api
import yaml
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from graphrag.config.create_graphrag_config import create_graphrag_config

from graphrag_app.logger.load_logger import load_pipeline_logger
from graphrag_app.utils.azure_clients import AzureClientManager
from graphrag_app.utils.common import sanitize_name

prompt_tuning_route = APIRouter(prefix="/index/config", tags=["Prompt Tuning"])


@prompt_tuning_route.get(
    "/prompts",
    summary="Generate custom graphrag prompts based on user-provided data.",
    description="Generating custom prompts from user-provided data may take several minutes to run based on the amount of data used.",
)
async def generate_prompts(
    container_name: str,
    limit: int = 5,
    sanitized_container_name: str = Depends(sanitize_name),
):
    """
    Automatically generate custom prompts for entity entraction,
    community reports, and summarize descriptions based on a sample of provided data.
    """
    # check for storage container existence
    azure_client_manager = AzureClientManager()
    blob_service_client = azure_client_manager.get_blob_service_client()
    if not blob_service_client.get_container_client(sanitized_container_name).exists():
        raise HTTPException(
            status_code=500,
            detail=f"Storage container '{container_name}' does not exist.",
        )

    # load pipeline configuration file (settings.yaml) for input data and other settings
    ROOT_DIR = Path(__file__).resolve().parent.parent.parent
    with (ROOT_DIR / "scripts/settings.yaml").open("r") as f:
        data = yaml.safe_load(f)
    data["input"]["container_name"] = sanitized_container_name
    graphrag_config = create_graphrag_config(values=data, root_dir=".")

    # generate prompts
    try:
        prompts: tuple[str, str, str] = await api.generate_indexing_prompts(
            config=graphrag_config,
            root=".",
            limit=limit,
            selection_method="random",
        )
    except Exception as e:
        logger = load_pipeline_logger()
        error_details = {
            "storage_name": container_name,
        }
        logger.error(
            message="Auto-prompt generation failed.",
            cause=e,
            stack=traceback.format_exc(),
            details=error_details,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error generating prompts for data in '{container_name}'. Please try a lower limit.",
        )

    prompt_content = {
        "entity_extraction_prompt": prompts[0],
        "entity_summarization_prompt": prompts[1],
        "community_summarization_prompt": prompts[2],
    }
    return prompt_content  # returns a fastapi.responses.JSONResponse object
