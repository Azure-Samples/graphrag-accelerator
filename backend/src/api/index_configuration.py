# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
from typing import Union

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from src.api.azure_clients import AzureStorageClientManager
from src.api.common import (
    sanitize_container_name,
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


@index_configuration_route.get(
    "/entity",
    summary="Get all entity configurations",
    response_model=EntityNameList,
    responses={200: {"model": EntityNameList}, 400: {"model": EntityNameList}},
)
def get_all_entitys():
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
    except Exception as e:
        reporter = ReporterSingleton.get_instance()
        reporter.on_error(f"Error getting all entity configurations: {str(e)}")
    return EntityNameList(entity_configuration_name=items)


@index_configuration_route.post(
    "/entity",
    summary="Create an entity configuration",
    response_model=BaseResponse,
    responses={200: {"model": BaseResponse}},
)
def create_entity(request: EntityConfiguration):
    # check for entity configuration existence
    entity_container = azure_storage_client_manager.get_cosmos_container_client(
        database_name="graphrag", container_name="entities"
    )
    sanitized_config_name = sanitize_container_name(request.entity_configuration_name)
    try:
        # throw error if entity configuration already exists
        entity_container.read_item(sanitized_config_name, sanitized_config_name)
        raise HTTPException(
            status_code=500,
            detail=f"{request.entity_configuration_name} already exists.",
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
                status=f"Entity:{entity} does not have an associated example."
            )
    entity_container.create_item(
        {
            "id": sanitized_config_name,
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
)
def update_entity(request: EntityConfiguration):
    # check for entity configuration existence
    reporter = ReporterSingleton.get_instance()
    existing_item = None
    try:
        entity_container = azure_storage_client_manager.get_cosmos_container_client(
            database_name="graphrag", container_name="entities"
        )
        sanitized_config_name = sanitize_container_name(
            request.entity_configuration_name
        )
        existing_item = entity_container.read_item(
            item=sanitized_config_name,
            partition_key=sanitized_config_name,
        )
    except Exception as e:
        reporter.on_error(f"Error getting entity type: {str(e)}")
        reporter.on_error(
            f"Item with entityConfigurationName '{request.entity_configuration_name}' not found."
        )
        raise HTTPException(
            status_code=500, detail=f"{request.entity_configuration_name} not found."
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
                    status=f"Entity: {entity} does not have an example associated."
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
    except Exception as e:
        reporter.on_error(f"Error updating entity type: {str(e)}")
    return BaseResponse(status="Success.")


@index_configuration_route.get(
    "/entity/{entity_configuration_name}",
    summary="Get a specified entity configuration",
    response_model=Union[EntityConfiguration, BaseResponse],
    responses={200: {"model": EntityConfiguration}, 400: {"model": BaseResponse}},
)
def get_entity(entity_configuration_name: str):
    reporter = ReporterSingleton.get_instance()
    try:
        existing_item = None
        entity_container = azure_storage_client_manager.get_cosmos_container_client(
            database_name="graphrag", container_name="entities"
        )
        sanitized_config_name = sanitize_container_name(entity_configuration_name)
        existing_item = entity_container.read_item(
            item=sanitized_config_name,
            partition_key=sanitized_config_name,
        )
        return EntityConfiguration(
            entity_configuration_name=existing_item["human_readable_name"],
            entity_types=existing_item["entity_types"],
            entity_examples=existing_item["entity_examples"],
        )
    except Exception as e:
        reporter.on_error(f"Error getting entity type: {str(e)}")
        reporter.on_error(
            f"Item with entity_configuration_name: {entity_configuration_name} not found."
        )
        raise HTTPException(
            status_code=500, detail=f"{entity_configuration_name} not found."
        )


@index_configuration_route.delete(
    "/entity/{entity_configuration_name}",
    summary="Delete a specified entity configuration",
    response_model=BaseResponse,
    responses={200: {"model": BaseResponse}},
)
def delete_entity(entity_configuration_name: str):
    reporter = ReporterSingleton.get_instance()
    try:
        entity_container = azure_storage_client_manager.get_cosmos_container_client(
            database_name="graphrag", container_name="entities"
        )
        sanitized_config_name = sanitize_container_name(entity_configuration_name)
        entity_container.delete_item(
            item=sanitized_config_name,
            partition_key=sanitized_config_name,
        )
        return BaseResponse(status="Success")
    except Exception as e:
        reporter.on_error(f"Error deleting entity type: {str(e)}")
        reporter.on_error(
            f"Item with entity_configuration_name {entity_configuration_name} not found."
        )
        raise HTTPException(
            status_code=500, detail=f"{entity_configuration_name} not found."
        )
