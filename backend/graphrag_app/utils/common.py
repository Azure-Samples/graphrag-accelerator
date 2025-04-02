# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import hashlib
import os
import sys
import traceback
from typing import Annotated
from pathlib import Path
from typing import Dict, List

import pandas as pd
from azure.core.exceptions import ResourceNotFoundError
from azure.cosmos import ContainerProxy, exceptions
from azure.identity import DefaultAzureCredential
from azure.storage.blob.aio import ContainerClient
from fastapi import Header, HTTPException
from graphrag.config.load_config import load_config
from graphrag.config.models.graph_rag_config import GraphRagConfig
from graphrag.config.models.vector_store_config import VectorStoreConfig

from graphrag_app.logger.load_logger import load_pipeline_logger
from graphrag_app.typing.models import QueryData
from graphrag_app.utils.azure_clients import AzureClientManager


def get_df(
    table_path: str,
) -> pd.DataFrame:
    df = pd.read_parquet(
        table_path,
        storage_options=pandas_storage_options(),
    )
    return df


def pandas_storage_options() -> dict:
    """Generate the storage options required by pandas to read parquet files from Storage."""
    # For more information on the options available, see: https://github.com/fsspec/adlfs?tab=readme-ov-file#setting-credentials
    azure_client_manager = AzureClientManager()
    options = {
        "account_name": azure_client_manager.storage_account_name,
        "account_host": azure_client_manager.storage_account_hostname,
    }
    if os.getenv("STORAGE_CONNECTION_STRING"):
        options["connection_string"] = os.getenv("STORAGE_CONNECTION_STRING")
    else:
        options["credential"] = DefaultAzureCredential()
    return options


def delete_storage_container_if_exist(container_name: str):
    """
    Delete a blob container. If it does not exist, do nothing.
    If exception is raised, the calling function should catch it.
    """
    azure_client_manager = AzureClientManager()
    blob_service_client = azure_client_manager.get_blob_service_client()
    try:
        blob_service_client.delete_container(container_name)
    except ResourceNotFoundError:
        # do nothing if container does not exist
        pass


def delete_cosmos_container_item_if_exist(container: str, item_id: str):
    """
    Delete an item from a cosmosdb container. If it does not exist, do nothing.
    If exception is raised, the calling function should catch it.
    """
    azure_client_manager = AzureClientManager()
    try:
        azure_client_manager.get_cosmos_container_client(
            database="graphrag", container=container
        ).delete_item(item_id, item_id)
    except ResourceNotFoundError:
        # do nothing if item does not exist
        pass


def validate_index_file_exist(sanitized_container_name: str, file_name: str):
    """
    Check if index exists and that the specified blob file exists.

    A "valid" index is defined by having an entry in the container-store table in cosmos db.
    Further checks are done to ensure the blob container and file exist.

    Args:
    -----
    sanitized_container_name (str)
        Sanitized name of a blob container.
    file_name (str)
        The blob file to be validated.

    Raises: ValueError
    """
    azure_client_manager = AzureClientManager()
    original_container_name = desanitize_name(sanitized_container_name)
    try:
        cosmos_container_client = get_cosmos_container_store_client()
        cosmos_container_client.read_item(
            sanitized_container_name, sanitized_container_name
        )
    except Exception:
        raise ValueError(f"{original_container_name} is not a valid index.")
    # check for file existence
    index_container_client = (
        azure_client_manager.get_blob_service_client().get_container_client(
            sanitized_container_name
        )
    )
    if not index_container_client.exists():
        raise ValueError(f"{original_container_name} not found.")
    if not index_container_client.get_blob_client(file_name).exists():
        raise ValueError(
            f"File {file_name} unavailable for container {original_container_name}."
        )


def get_cosmos_container_store_client() -> ContainerProxy:
    try:
        azure_client_manager = AzureClientManager()
        return azure_client_manager.get_cosmos_container_client(
            database="graphrag", container="container-store"
        )
    except Exception as e:
        logger = load_pipeline_logger()
        logger.error(
            message="Error fetching cosmosdb client.",
            cause=e,
            stack=traceback.format_exc(),
        )
        raise HTTPException(status_code=500, detail="Error fetching cosmosdb client.")


async def get_blob_container_client(name: str) -> ContainerClient:
    try:
        azure_client_manager = AzureClientManager()
        blob_service_client = azure_client_manager.get_blob_service_client_async()
        container_client = blob_service_client.get_container_client(name)
        if not await container_client.exists():
            await container_client.create_container()
        return container_client
    except Exception as e:
        logger = load_pipeline_logger()
        logger.error(
            message="Error fetching storage client.",
            cause=e,
            stack=traceback.format_exc(),
        )
        raise HTTPException(status_code=500, detail="Error fetching storage client.")


def sanitize_name(container_name: str) -> str:
    """
    Sanitize a user-provided string to be used as an Azure Storage container name.
    Convert the string to a SHA256 hash, then truncate to 128 bit length to ensure
    it is within the 63 character limit imposed by Azure Storage.

    The sanitized name will be used to identify container names in both Azure Storage and CosmosDB.

    Args:
    -----
    name (str)
        The name to be sanitized.

    Returns: str
        The sanitized name.
    """
    container_name = container_name.encode()
    hashed_name = hashlib.sha256(container_name)
    truncated_hash = hashed_name.digest()[:16]  # get the first 16 bytes (128 bits)
    return truncated_hash.hex()


def desanitize_name(sanitized_container_name: str) -> str | None:
    """
    Reverse the sanitization process by retrieving the original user-provided name.

    Args:
    -----
    sanitized_name (str)
        The sanitized name to be converted back to the original name.

    Returns: str | None
        The original human-readable name or None if it does not exist.
    """
    try:
        container_store_client = get_cosmos_container_store_client()
        try:
            return container_store_client.read_item(
                sanitized_container_name, sanitized_container_name
            )["human_readable_name"]
        except exceptions.CosmosResourceNotFoundError:
            return None
    except Exception:
        raise HTTPException(
            status_code=500, detail="Error retrieving original container name."
        )


async def subscription_key_check(
    Ocp_Apim_Subscription_Key: Annotated[str, Header()],
):
    """
    Verifies if user has passed the Ocp_Apim_Subscription_Key (APIM subscription key) in the request header.
    If it is not present, an HTTPException with a 400 status code is raised.
    Note: this check is unnecessary (APIM validates subscription keys automatically), but this will add the key
    as a required parameter in the swagger docs page, enabling users to send requests using the swagger docs "Try it out" feature.
    """
    if not Ocp_Apim_Subscription_Key:
        raise HTTPException(
            status_code=400, detail="Ocp-Apim-Subscription-Key required"
        )
    return Ocp_Apim_Subscription_Key


def get_data_tables(
        index_names: Dict[str, str],
        community_level: int = -1,
        include_local_context: bool = True
    ) -> QueryData:
    """
    Get the data tables for the given index names.

    Args:
        index_names (str | List[str]): The index names.

    Returns:
        QueryData: The data objects for the given index names.
    """
    logger = load_pipeline_logger()

    COMMUNITY_TABLE = "output/communities.parquet"
    COMMUNITY_REPORT_TABLE = "output/community_reports.parquet"
    COVARIATES_TABLE = "output/covariates.parquet"
    ENTITIES_TABLE = "output/entities.parquet"
    RELATIONSHIPS_TABLE = "output/relationships.parquet"
    TEXT_UNITS_TABLE = "output/text_units.parquet"

    if isinstance(community_level, int):
        COMMUNITY_LEVEL = community_level
    elif isinstance(community_level, float):
        COMMUNITY_LEVEL = int(community_level)
    else:
        # community level 1 is best for local and drift search, level 2 is best got global search
        COMMUNITY_LEVEL = 1 if include_local_context else 2

    if COMMUNITY_LEVEL == -1:
        # get all available communities when the community level is set to -1
        COMMUNITY_LEVEL = sys.maxsize  # get the largest possible integer in python

    sanitized_name = index_names["sanitized_name"]

    # check for existence of files the query relies on to validate the index is complete
    validate_index_file_exist(sanitized_name, COMMUNITY_TABLE)
    validate_index_file_exist(sanitized_name, COMMUNITY_REPORT_TABLE)
    validate_index_file_exist(sanitized_name, ENTITIES_TABLE)
    validate_index_file_exist(sanitized_name, RELATIONSHIPS_TABLE)
    validate_index_file_exist(sanitized_name, TEXT_UNITS_TABLE)

    # load community reports data
    communities_df = get_df(f"abfs://{sanitized_name}/{COMMUNITY_TABLE}")
    communities_df[communities_df.level <= COMMUNITY_LEVEL]

    # load community reports data
    community_report_df = get_df(f"abfs://{sanitized_name}/{COMMUNITY_REPORT_TABLE}")
    community_report_df[community_report_df.level <= COMMUNITY_LEVEL]
    
    entities_df = get_df(f"abfs://{sanitized_name}/{ENTITIES_TABLE}")
    
    if include_local_context:
        # we only need to get these tables when we are not doing a global query
        text_units_df = get_df(f"abfs://{sanitized_name}/{TEXT_UNITS_TABLE}")
        relationships_df = get_df(f"abfs://{sanitized_name}/{RELATIONSHIPS_TABLE}")
        covariates_df = None
        try:
            covariates_df = get_df(f"abfs://{sanitized_name}/{COVARIATES_TABLE}")
        except Exception as e:
            logger.warning(f"Covariates table not found: {e}")

    # load custom pipeline settings
    ROOT_DIR = Path(__file__).resolve().parent.parent.parent / "scripts/settings.yaml"
    
    # layer the custom settings on top of the default configuration settings of graphrag
    config: GraphRagConfig = load_config(
        root_dir=ROOT_DIR.parent, 
        config_filepath=ROOT_DIR
    )
    # dynamically assign the sanitized index name 
    config.vector_store["default_vector_store"].container_name = sanitized_name
    
    data = QueryData(
        communities=communities_df,
        community_reports=community_report_df,
        entities=entities_df,
        community_level=COMMUNITY_LEVEL,
        config=config,
    )
    if include_local_context:
        # add local context to the data object
        data.text_units = text_units_df
        data.relationships = relationships_df
        data.covariates = covariates_df
    return data


def update_multi_index_context_data(
    context_data,
    index_name: str,
    index_id: str,
):
    """
    Update context data with the links dict so that it contains both the index name and community id.

    Parameters
    ----------
    - context_data (str | list[pd.DataFrame] | dict[str, pd.DataFrame]): The context data to update.
    - index_name (str): The name of the index.
    - index_id (str): The id of the index.

    Returns
    -------
    str | list[pd.DataFrame] | dict[str, pd.DataFrame]: The updated context data.
    """
    updated_context_data = {}
    for key in context_data:
        updated_entry = []
        if key == "reports":
            updated_entry = [
                {
                    **entry,
                    "index_name": index_name,
                    "index_id": index_id,
                } 
                for entry in context_data[key].to_dict(orient="records")
            ]
        if key == "entities":
            updated_entry = [
                {
                    **entry,
                    "index_name": index_name,
                    "index_id": index_id,
                }
                for entry in context_data[key].to_dict(orient="records")
            ]
        if key == "relationships":
            updated_entry = [
                {
                    **entry,
                    "index_name": index_name,
                    "index_id": index_id,
                }
                for entry in context_data[key].to_dict(orient="records")
            ]
        if key == "claims":
            updated_entry = [
                {
                    **entry,
                    "index_name": index_name,
                    "index_id": index_id,
                }
                for entry in context_data[key].to_dict(orient="records")
            ]
        if key == "sources":
            updated_entry = [
                {
                    **entry,
                    "index_name": index_name,
                    "index_id": index_id,
                }
                for entry in context_data[key].to_dict(orient="records")
            ]
        updated_context_data[key] = updated_entry
    return updated_context_data
    