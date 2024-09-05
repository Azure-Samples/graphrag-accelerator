# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import inspect
import os
import shutil
from typing import Union

import yaml
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from fastapi.responses import StreamingResponse
from graphrag.prompt_tune.cli import prompt_tune as generate_fine_tune_prompts

from src.api.azure_clients import (
    AzureStorageClientManager,
    BlobServiceClientSingleton,
)
from src.api.common import (
    sanitize_name,
    verify_subscription_key_exist,
)
from src.models import (
    BaseResponse,
    EntityConfiguration,
    EntityNameList,
)
from src.reporting import ReporterSingleton

azure_storage_client_manager = AzureStorageClientManager()
index_configuration_route = APIRouter(
    prefix="/index/config", tags=["Index Configuration"]
)

if os.getenv("KUBERNETES_SERVICE_HOST"):
    index_configuration_route.dependencies.append(
        Depends(verify_subscription_key_exist)
    )

# NOTE: currently disable all /entity endpoints - to be replaced by the auto-generation of prompts


@index_configuration_route.get(
    "/entity",
    summary="Get all entity configurations",
    response_model=EntityNameList,
    responses={200: {"model": EntityNameList}, 400: {"model": EntityNameList}},
    include_in_schema=False,
)
async def get_all_entitys():
    """
    Retrieve a list of all entity configuration names.
    """
    items = []
    try:
        entity_container = azure_storage_client_manager.get_cosmos_container_client(
            database_name="graphrag", container_name="entities"
        )
        for item in entity_container.read_all_items():
            items.append(item["human_readable_name"])
    except Exception:
        reporter = ReporterSingleton.get_instance()
        reporter.on_error("Error getting all entity configurations")
    return EntityNameList(entity_configuration_name=items)


@index_configuration_route.post(
    "/entity",
    summary="Create an entity configuration",
    response_model=BaseResponse,
    responses={200: {"model": BaseResponse}},
    include_in_schema=False,
)
async def create_entity(request: EntityConfiguration):
    # check for entity configuration existence
    entity_container = azure_storage_client_manager.get_cosmos_container_client(
        database_name="graphrag", container_name="entities"
    )
    sanitized_entity_config_name = sanitize_name(request.entity_configuration_name)
    try:
        # throw error if entity configuration already exists
        entity_container.read_item(
            item=sanitized_entity_config_name,
            partition_key=sanitized_entity_config_name,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Entity configuration name '{request.entity_configuration_name}' already exists.",
        )
    except Exception:
        pass

    # create entity configuration and add to database
    all_examples = ""
    entity_examples = []
    for example in request.entity_examples:
        if (
            len(example.entity_types) == 0
            or len(example.text) == 0
            or len(example.output) == 0
        ):
            return BaseResponse(status="Example contains empty parameters")
        all_examples += example.entity_types
        entity_examples.append(
            {
                "entity_types": example.entity_types,
                "text": example.text,
                "output": example.output,
            }
        )
    for entity in request.entity_types:
        if entity not in all_examples:
            return BaseResponse(
                status=f"Entity '{entity}' does not have an associated example."
            )
    entity_container.create_item(
        {
            "id": sanitized_entity_config_name,
            "human_readable_name": request.entity_configuration_name,
            "entity_types": request.entity_types,
            "entity_examples": entity_examples,
        }
    )
    return BaseResponse(status="Success")


@index_configuration_route.put(
    "/entity",
    summary="Update an existing entity configuration",
    response_model=BaseResponse,
    responses={200: {"model": BaseResponse}},
    include_in_schema=False,
)
async def update_entity(request: EntityConfiguration):
    # check for entity configuration existence
    reporter = ReporterSingleton.get_instance()
    existing_item = None
    try:
        entity_container = azure_storage_client_manager.get_cosmos_container_client(
            database_name="graphrag", container_name="entities"
        )
        sanitized_config_name = sanitize_name(request.entity_configuration_name)
        existing_item = entity_container.read_item(
            item=sanitized_config_name,
            partition_key=sanitized_config_name,
        )
    except Exception:
        reporter.on_error("Error getting entity type")
        reporter.on_error(
            f"Item with entity configuration name '{request.entity_configuration_name}' not found."
        )
        raise HTTPException(
            status_code=500,
            detail=f"Entity configuration '{request.entity_configuration_name}' not found.",
        )
    # update entity configuration and add back to database
    try:
        all_examples = ""
        for example in request.entity_examples:
            if (
                len(example.entity_types) == 0
                or len(example.text) == 0
                or len(example.output) == 0
            ):
                return BaseResponse(status="Example contains empty parameters")
            all_examples += example.entity_types
        for entity in request.entity_types:
            if entity not in all_examples:
                return BaseResponse(
                    status=f"Entity '{entity}' does not have an example associated."
                )
        # Update the existing item with the new information if it is different
        if existing_item["entity_types"] != request.entity_types:
            existing_item["entity_types"] = request.entity_types
        if existing_item["entity_examples"] != request.entity_examples:
            existing_item["entity_examples"] = [
                {"entity_types": i.entity_types, "text": i.text, "output": i.output}
                for i in request.entity_examples
            ]
        entity_container.replace_item(sanitized_config_name, existing_item)
    except Exception:
        reporter.on_error("Error updating entity type")
    return BaseResponse(status="Success.")


@index_configuration_route.get(
    "/entity/{entity_configuration_name}",
    summary="Get a specified entity configuration",
    response_model=Union[EntityConfiguration, BaseResponse],
    responses={200: {"model": EntityConfiguration}, 400: {"model": BaseResponse}},
    include_in_schema=False,
)
async def get_entity(entity_configuration_name: str):
    reporter = ReporterSingleton.get_instance()
    try:
        existing_item = None
        entity_container = azure_storage_client_manager.get_cosmos_container_client(
            database_name="graphrag", container_name="entities"
        )
        sanitized_config_name = sanitize_name(entity_configuration_name)
        existing_item = entity_container.read_item(
            item=sanitized_config_name,
            partition_key=sanitized_config_name,
        )
        return EntityConfiguration(
            entity_configuration_name=existing_item["human_readable_name"],
            entity_types=existing_item["entity_types"],
            entity_examples=existing_item["entity_examples"],
        )
    except Exception:
        reporter.on_error("Error getting entity type")
        reporter.on_error(
            f"Item with entity configuration name '{entity_configuration_name}' not found."
        )
        raise HTTPException(
            status_code=500,
            detail=f"Entity configuration '{entity_configuration_name}' not found.",
        )


@index_configuration_route.delete(
    "/entity/{entity_configuration_name}",
    summary="Delete a specified entity configuration",
    response_model=BaseResponse,
    responses={200: {"model": BaseResponse}},
    include_in_schema=False,
)
async def delete_entity(entity_configuration_name: str):
    reporter = ReporterSingleton.get_instance()
    try:
        entity_container = azure_storage_client_manager.get_cosmos_container_client(
            database_name="graphrag", container_name="entities"
        )
        sanitized_entity_config_name = sanitize_name(entity_configuration_name)
        entity_container.delete_item(
            item=sanitized_entity_config_name,
            partition_key=sanitized_entity_config_name,
        )
        return BaseResponse(status="Success")
    except Exception:
        reporter.on_error("Error deleting entity")
        reporter.on_error(
            f"Item with entity configuration name '{entity_configuration_name}' not found."
        )
        raise HTTPException(
            status_code=500,
            detail=f"Entity configuration '{entity_configuration_name}' not found.",
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
    blob_service_client = BlobServiceClientSingleton().get_instance()
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
            config = f"{temp_dir}/settings.yaml",
            root = temp_dir,
            domain = "",
            selection_method = "random",
            limit = limit,
            skip_entity_types = True,
            output = "prompts",
        )
    except Exception:
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
