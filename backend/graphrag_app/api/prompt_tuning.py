# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import traceback
from pathlib import Path

import graphrag.api as api
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from graphrag.config.load_config import load_config
from graphrag.config.models.graph_rag_config import GraphRagConfig
from graphrag.logger.rich_progress import RichProgressLogger
from graphrag.prompt_tune.types import DocSelectionType

from graphrag_app.logger.load_logger import load_pipeline_logger
from graphrag_app.utils.azure_clients import AzureClientManager
from graphrag_app.utils.common import sanitize_name, subscription_key_check

prompt_tuning_route = APIRouter(prefix="/index/config", tags=["Prompt Tuning"])
if os.getenv("KUBERNETES_SERVICE_HOST"):
    prompt_tuning_route.dependencies.append(Depends(subscription_key_check))


@prompt_tuning_route.get(
    "/prompts",
    summary="Generate custom graphrag prompts based on user-provided data.",
    description="Generating custom prompts from user-provided data may take several minutes to run based on the amount of data used.",
    status_code=status.HTTP_200_OK,
)
async def generate_prompts(
    container_name: str,
    limit: int = 15,
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

    # load custom pipeline settings
    ROOT_DIR = Path(__file__).resolve().parent.parent.parent / "scripts/settings.yaml"
    
    # layer the custom settings on top of the default configuration settings of graphrag
    graphrag_config: GraphRagConfig = load_config(
        root_dir=ROOT_DIR.parent, 
        config_filepath=ROOT_DIR
    )
    graphrag_config.input.container_name = sanitized_container_name

    # generate prompts
    try:
        prompts: tuple[str, str, str] = await api.generate_indexing_prompts(
            config=graphrag_config,
            logger=RichProgressLogger(prefix=sanitized_container_name),
            root=".",
            limit=limit,
            selection_method=DocSelectionType.AUTO,
        )
        prompt_content = {
            "entity_extraction_prompt": prompts[0],
            "entity_summarization_prompt": prompts[1],
            "community_summarization_prompt": prompts[2],
        }
        return prompt_content  # returns a fastapi.responses.JSONResponse object
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