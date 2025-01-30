# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import traceback
from pathlib import Path

import yaml
from fastapi import (
    APIRouter,
    HTTPException,
)
from graphrag.api.query import global_search, local_search
from graphrag.config.create_graphrag_config import create_graphrag_config

from graphrag_app.logger.load_logger import load_pipeline_logger
from graphrag_app.typing.models import (
    GraphRequest,
    GraphResponse,
)
from graphrag_app.typing.pipeline import PipelineJobState
from graphrag_app.utils.azure_clients import AzureClientManager
from graphrag_app.utils.common import (
    get_df,
    sanitize_name,
    validate_index_file_exist,
)
from graphrag_app.utils.pipeline import PipelineJob

query_route = APIRouter(
    prefix="/query",
    tags=["Query Operations"],
)


@query_route.post(
    "/global",
    summary="Perform a global search across the knowledge graph index",
    description="The global query method generates answers by searching over all AI-generated community reports in a map-reduce fashion. This is a resource-intensive method, but often gives good responses for questions that require an understanding of the dataset as a whole.",
    response_model=GraphResponse,
    responses={200: {"model": GraphResponse}},
)
async def global_query(request: GraphRequest):
    # this is a slightly modified version of the graphrag.query.cli.run_global_search method
    index_name = request.index_name
    sanitized_index_name = sanitize_name(index_name)

    if not _is_index_complete(sanitized_index_name):
        raise HTTPException(
            status_code=500,
            detail=f"{index_name} not ready for querying.",
        )

    COMMUNITY_REPORT_TABLE = "output/create_final_community_reports.parquet"
    COMMUNITIES_TABLE = "output/create_final_communities.parquet"
    ENTITIES_TABLE = "output/create_final_entities.parquet"
    NODES_TABLE = "output/create_final_nodes.parquet"

    validate_index_file_exist(sanitized_index_name, COMMUNITY_REPORT_TABLE)
    validate_index_file_exist(sanitized_index_name, ENTITIES_TABLE)
    validate_index_file_exist(sanitized_index_name, NODES_TABLE)

    if isinstance(request.community_level, int):
        COMMUNITY_LEVEL = request.community_level
    else:
        # Current investigations show that community level 1 is the most useful for global search. Set this as the default value
        COMMUNITY_LEVEL = 1

    try:
        # read the parquet files into DataFrames and add provenance information
        community_report_table_path = (
            f"abfs://{sanitized_index_name}/{COMMUNITY_REPORT_TABLE}"
        )
        communities_table_path = f"abfs://{sanitized_index_name}/{COMMUNITIES_TABLE}"
        entities_table_path = f"abfs://{sanitized_index_name}/{ENTITIES_TABLE}"
        nodes_table_path = f"abfs://{sanitized_index_name}/{NODES_TABLE}"

        # load parquet tables associated with the index
        nodes_df = get_df(nodes_table_path)
        community_reports_df = get_df(community_report_table_path)
        communities_df = get_df(communities_table_path)
        entities_df = get_df(entities_table_path)

        # load custom pipeline settings
        ROOT_DIR = Path(__file__).resolve().parent.parent.parent
        with (ROOT_DIR / "scripts/settings.yaml").open("r") as f:
            data = yaml.safe_load(f)

        # layer the custom settings on top of the default configuration settings of graphrag
        parameters = create_graphrag_config(data, ".")

        # perform async search
        result = await global_search(
            config=parameters,
            nodes=nodes_df,
            entities=entities_df,
            communities=communities_df,
            community_reports=community_reports_df,
            community_level=COMMUNITY_LEVEL,
            dynamic_community_selection=False,
            response_type="Multiple Paragraphs",
            query=request.query,
        )

        return GraphResponse(result=result[0], context_data=result[1])
    except Exception as e:
        logger = load_pipeline_logger()
        logger.error(
            message="Could not perform global search.",
            cause=e,
            stack=traceback.format_exc(),
        )
        raise HTTPException(status_code=500, detail=None)


@query_route.post(
    "/local",
    summary="Perform a local search across the knowledge graph index.",
    description="The local query method generates answers by combining relevant data from the AI-extracted knowledge-graph with text chunks of the raw documents. This method is suitable for questions that require an understanding of specific entities mentioned in the documents (e.g. What are the healing properties of chamomile?).",
    response_model=GraphResponse,
    responses={200: {"model": GraphResponse}},
)
async def local_query(request: GraphRequest):
    index_name = request.index_name
    sanitized_index_name = sanitize_name(index_name)

    if not _is_index_complete(sanitized_index_name):
        raise HTTPException(
            status_code=500,
            detail=f"{index_name} not ready for querying.",
        )

    azure_client_manager = AzureClientManager()
    blob_service_client = azure_client_manager.get_blob_service_client()

    COMMUNITY_REPORT_TABLE = "output/create_final_community_reports.parquet"
    COVARIATES_TABLE = "output/create_final_covariates.parquet"
    ENTITIES_TABLE = "output/create_final_entities.parquet"
    NODES_TABLE = "output/create_final_nodes.parquet"
    RELATIONSHIPS_TABLE = "output/create_final_relationships.parquet"
    TEXT_UNITS_TABLE = "output/create_final_text_units.parquet"

    if isinstance(request.community_level, int):
        COMMUNITY_LEVEL = request.community_level
    else:
        # Current investigations show that community level 2 is the most useful for local search. Set this as the default value
        COMMUNITY_LEVEL = 2

    # check for existence of files the query relies on to validate the index is complete
    validate_index_file_exist(sanitized_index_name, COMMUNITY_REPORT_TABLE)
    validate_index_file_exist(sanitized_index_name, ENTITIES_TABLE)
    validate_index_file_exist(sanitized_index_name, NODES_TABLE)
    validate_index_file_exist(sanitized_index_name, RELATIONSHIPS_TABLE)
    validate_index_file_exist(sanitized_index_name, TEXT_UNITS_TABLE)

    community_report_table_path = (
        f"abfs://{sanitized_index_name}/{COMMUNITY_REPORT_TABLE}"
    )
    covariates_table_path = f"abfs://{sanitized_index_name}/{COVARIATES_TABLE}"
    entities_table_path = f"abfs://{sanitized_index_name}/{ENTITIES_TABLE}"
    nodes_table_path = f"abfs://{sanitized_index_name}/{NODES_TABLE}"
    relationships_table_path = f"abfs://{sanitized_index_name}/{RELATIONSHIPS_TABLE}"
    text_units_table_path = f"abfs://{sanitized_index_name}/{TEXT_UNITS_TABLE}"

    nodes_df = get_df(nodes_table_path)
    community_reports_df = get_df(community_report_table_path)
    entities_df = get_df(entities_table_path)
    relationships_df = get_df(relationships_table_path)
    text_units_df = get_df(text_units_table_path)

    # If present, prepare each index's covariates dataframe for merging
    index_container_client = blob_service_client.get_container_client(
        sanitized_index_name
    )
    covariates_df = None
    if index_container_client.get_blob_client(COVARIATES_TABLE).exists():
        covariates_df = get_df(covariates_table_path)

    # load custom pipeline settings
    ROOT_DIR = Path(__file__).resolve().parent.parent.parent
    with (ROOT_DIR / "scripts/settings.yaml").open("r") as f:
        data = yaml.safe_load(f)

    # layer the custom settings on top of the default configuration settings of graphrag
    parameters = create_graphrag_config(data, ".")
    # add index_names to vector_store args
    parameters.embeddings.vector_store["collection_name"] = sanitized_index_name

    # perform async search
    result = await local_search(
        config=parameters,
        nodes=nodes_df,
        entities=entities_df,
        community_reports=community_reports_df,
        text_units=text_units_df,
        relationships=relationships_df,
        covariates=covariates_df,
        community_level=COMMUNITY_LEVEL,
        response_type="Multiple Paragraphs",
        query=request.query,
    )

    return GraphResponse(result=result[0], context_data=result[1])


def _is_index_complete(index_name: str) -> bool:
    """
    Check if an index is ready for querying.

    An index is ready for use only if it exists in the jobs table in cosmos db and
    the indexing build job has finished (i.e. 100 percent). Otherwise it is not ready.

    Args:
    -----
    index_name (str)
        Name of the index to check.

    Returns: bool
        True if the index is ready for use, False otherwise.
    """
    if PipelineJob.item_exist(index_name):
        pipeline_job = PipelineJob.load_item(index_name)
        if PipelineJobState(pipeline_job.status) == PipelineJobState.COMPLETE:
            return True
    return False
