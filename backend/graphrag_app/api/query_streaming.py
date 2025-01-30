# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import inspect
import json
import os
import traceback

import pandas as pd
import yaml
from fastapi import (
    APIRouter,
    HTTPException,
)
from fastapi.responses import StreamingResponse
from graphrag.api.query import (
    global_search_streaming as global_search_streaming_internal,
)
from graphrag.api.query import (
    local_search_streaming as local_search_streaming_internal,
)
from graphrag.config import create_graphrag_config

from graphrag_app.api.query import _is_index_complete
from graphrag_app.logger.load_logger import load_pipeline_logger
from graphrag_app.typing.models import GraphRequest
from graphrag_app.utils.azure_clients import AzureClientManager
from graphrag_app.utils.common import (
    get_df,
    sanitize_name,
    validate_index_file_exist,
)

from .query import _get_embedding_description_store, _update_context

query_streaming_route = APIRouter(
    prefix="/query/streaming",
    tags=["Query Streaming Operations"],
)


@query_streaming_route.post(
    "/global",
    summary="Stream a response back after performing a global search",
    description="The global query method generates answers by searching over all AI-generated community reports in a map-reduce fashion. This is a resource-intensive method, but often gives good responses for questions that require an understanding of the dataset as a whole.",
)
async def global_search_streaming(request: GraphRequest):
    # this is a slightly modified version of graphrag_app.api.query.global_query() method
    if isinstance(request.index_name, str):
        index_names = [request.index_name]
    else:
        index_names = request.index_name
    sanitized_index_names = [sanitize_name(name) for name in index_names]
    sanitized_index_names_link = {
        s: i for s, i in zip(sanitized_index_names, index_names)
    }

    for index_name in sanitized_index_names:
        if not _is_index_complete(index_name):
            raise HTTPException(
                status_code=500,
                detail=f"{sanitized_index_names_link[index_name]} not ready for querying.",
            )

    COMMUNITY_REPORT_TABLE = "output/create_final_community_reports.parquet"
    ENTITIES_TABLE = "output/create_final_entities.parquet"
    NODES_TABLE = "output/create_final_nodes.parquet"

    if isinstance(request.community_level, int):
        COMMUNITY_LEVEL = request.community_level
    else:
        # Current investigations show that community level 1 is the most useful for global search. Set this as the default value
        COMMUNITY_LEVEL = 1

    for index_name in sanitized_index_names:
        validate_index_file_exist(index_name, COMMUNITY_REPORT_TABLE)
        validate_index_file_exist(index_name, ENTITIES_TABLE)
        validate_index_file_exist(index_name, NODES_TABLE)
    try:
        links = {
            "nodes": {},
            "community": {},
            "entities": {},
            "text_units": {},
            "relationships": {},
            "covariates": {},
        }
        max_vals = {
            "nodes": -1,
            "community": -1,
            "entities": -1,
            "text_units": -1,
            "relationships": -1,
            "covariates": -1,
        }

        community_dfs = []
        entities_dfs = []
        nodes_dfs = []

        for index_name in sanitized_index_names:
            community_report_table_path = (
                f"abfs://{index_name}/{COMMUNITY_REPORT_TABLE}"
            )
            entities_table_path = f"abfs://{index_name}/{ENTITIES_TABLE}"
            nodes_table_path = f"abfs://{index_name}/{NODES_TABLE}"

            # read parquet files into DataFrames and add provenance information
            # note that nodes need to set before communities to that max community id makes sense
            nodes_df = get_df(nodes_table_path)
            for i in nodes_df["human_readable_id"]:
                links["nodes"][i + max_vals["nodes"] + 1] = {
                    "index_name": sanitized_index_names_link[index_name],
                    "id": i,
                }
            if max_vals["nodes"] != -1:
                nodes_df["human_readable_id"] += max_vals["nodes"] + 1
            nodes_df["community"] = nodes_df["community"].apply(
                lambda x: str(int(x) + max_vals["community"] + 1) if x else x
            )
            nodes_df["title"] = nodes_df["title"].apply(lambda x: x + f"-{index_name}")
            nodes_df["source_id"] = nodes_df["source_id"].apply(
                lambda x: ",".join([i + f"-{index_name}" for i in x.split(",")])
            )
            max_vals["nodes"] = nodes_df["human_readable_id"].max()
            nodes_dfs.append(nodes_df)

            community_df = get_df(community_report_table_path)
            for i in community_df["community"].astype(int):
                links["community"][i + max_vals["community"] + 1] = {
                    "index_name": sanitized_index_names_link[index_name],
                    "id": str(i),
                }
            if max_vals["community"] != -1:
                col = community_df["community"].astype(int) + max_vals["community"] + 1
                community_df["community"] = col.astype(str)
            max_vals["community"] = community_df["community"].astype(int).max()
            community_dfs.append(community_df)

            entities_df = get_df(entities_table_path)
            for i in entities_df["human_readable_id"]:
                links["entities"][i + max_vals["entities"] + 1] = {
                    "index_name": sanitized_index_names_link[index_name],
                    "id": i,
                }
            if max_vals["entities"] != -1:
                entities_df["human_readable_id"] += max_vals["entities"] + 1
            entities_df["name"] = entities_df["name"].apply(
                lambda x: x + f"-{index_name}"
            )
            entities_df["text_unit_ids"] = entities_df["text_unit_ids"].apply(
                lambda x: [i + f"-{index_name}" for i in x]
            )
            max_vals["entities"] = entities_df["human_readable_id"].max()
            entities_dfs.append(entities_df)

        # merge the dataframes
        nodes_combined = pd.concat(nodes_dfs, axis=0, ignore_index=True, sort=False)
        community_combined = pd.concat(
            community_dfs, axis=0, ignore_index=True, sort=False
        )
        entities_combined = pd.concat(
            entities_dfs, axis=0, ignore_index=True, sort=False
        )

        # load custom pipeline settings
        this_directory = os.path.dirname(
            os.path.abspath(inspect.getfile(inspect.currentframe()))
        )
        data = yaml.safe_load(open(f"{this_directory}/pipeline-settings.yaml"))
        # layer the custom settings on top of the default configuration settings of graphrag
        parameters = create_graphrag_config(data, ".")

        return StreamingResponse(
            _wrapper(
                global_search_streaming_internal(
                    config=parameters,
                    nodes=nodes_combined,
                    entities=entities_combined,
                    community_reports=community_combined,
                    community_level=COMMUNITY_LEVEL,
                    response_type="Multiple Paragraphs",
                    query=request.query,
                ),
                links,
            ),
            media_type="application/json",
        )
    except Exception as e:
        logger = load_pipeline_logger()
        logger.error(
            message="Error encountered while streaming global search response",
            cause=e,
            stack=traceback.format_exc(),
        )
        raise HTTPException(status_code=500, detail=None)


@query_streaming_route.post(
    "/local",
    summary="Stream a response back after performing a local search",
    description="The local query method generates answers by combining relevant data from the AI-extracted knowledge-graph with text chunks of the raw documents. This method is suitable for questions that require an understanding of specific entities mentioned in the documents (e.g. What are the healing properties of chamomile?).",
)
async def local_search_streaming(request: GraphRequest):
    # this is a slightly modified version of graphrag_app.api.query.local_query() method
    if isinstance(request.index_name, str):
        index_names = [request.index_name]
    else:
        index_names = request.index_name
    sanitized_index_names = [sanitize_name(name) for name in index_names]
    sanitized_index_names_link = {
        s: i for s, i in zip(sanitized_index_names, index_names)
    }
    for index_name in sanitized_index_names:
        if not _is_index_complete(index_name):
            raise HTTPException(
                status_code=500,
                detail=f"{sanitized_index_names_link[index_name]} not ready for querying.",
            )
    azure_client_manager = AzureClientManager()
    blob_service_client = azure_client_manager.get_blob_service_client()

    community_dfs = []
    covariates_dfs = []
    entities_dfs = []
    nodes_dfs = []
    relationships_dfs = []
    text_units_dfs = []
    links = {
        "nodes": {},
        "community": {},
        "entities": {},
        "text_units": {},
        "relationships": {},
        "covariates": {},
    }
    max_vals = {
        "nodes": -1,
        "community": -1,
        "entities": -1,
        "text_units": -1,
        "relationships": -1,
        "covariates": -1,
    }

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

    try:
        for index_name in sanitized_index_names:
            # check for existence of files the query relies on to validate the index is complete
            validate_index_file_exist(index_name, COMMUNITY_REPORT_TABLE)
            validate_index_file_exist(index_name, ENTITIES_TABLE)
            validate_index_file_exist(index_name, NODES_TABLE)
            validate_index_file_exist(index_name, RELATIONSHIPS_TABLE)
            validate_index_file_exist(index_name, TEXT_UNITS_TABLE)

            community_report_table_path = (
                f"abfs://{index_name}/{COMMUNITY_REPORT_TABLE}"
            )
            covariates_table_path = f"abfs://{index_name}/{COVARIATES_TABLE}"
            entities_table_path = f"abfs://{index_name}/{ENTITIES_TABLE}"
            nodes_table_path = f"abfs://{index_name}/{NODES_TABLE}"
            relationships_table_path = f"abfs://{index_name}/{RELATIONSHIPS_TABLE}"
            text_units_table_path = f"abfs://{index_name}/{TEXT_UNITS_TABLE}"

            # read the parquet files into DataFrames and add provenance information

            # note that nodes need to set before communities to that max community id makes sense
            nodes_df = get_df(nodes_table_path)
            for i in nodes_df["human_readable_id"]:
                links["nodes"][i + max_vals["nodes"] + 1] = {
                    "index_name": sanitized_index_names_link[index_name],
                    "id": i,
                }
            if max_vals["nodes"] != -1:
                nodes_df["human_readable_id"] += max_vals["nodes"] + 1
            nodes_df["community"] = nodes_df["community"].apply(
                lambda x: str(int(x) + max_vals["community"] + 1) if x else x
            )
            nodes_df["id"] = nodes_df["id"].apply(lambda x: x + f"-{index_name}")
            nodes_df["title"] = nodes_df["title"].apply(lambda x: x + f"-{index_name}")
            nodes_df["source_id"] = nodes_df["source_id"].apply(
                lambda x: ",".join([i + f"-{index_name}" for i in x.split(",")])
            )
            max_vals["nodes"] = nodes_df["human_readable_id"].max()
            nodes_dfs.append(nodes_df)

            community_df = get_df(community_report_table_path)
            for i in community_df["community"].astype(int):
                links["community"][i + max_vals["community"] + 1] = {
                    "index_name": sanitized_index_names_link[index_name],
                    "id": str(i),
                }
            if max_vals["community"] != -1:
                col = community_df["community"].astype(int) + max_vals["community"] + 1
                community_df["community"] = col.astype(str)
            max_vals["community"] = community_df["community"].astype(int).max()
            community_dfs.append(community_df)

            entities_df = get_df(entities_table_path)
            for i in entities_df["human_readable_id"]:
                links["entities"][i + max_vals["entities"] + 1] = {
                    "index_name": sanitized_index_names_link[index_name],
                    "id": i,
                }
            if max_vals["entities"] != -1:
                entities_df["human_readable_id"] += max_vals["entities"] + 1
            entities_df["id"] = entities_df["id"].apply(lambda x: x + f"-{index_name}")
            entities_df["name"] = entities_df["name"].apply(
                lambda x: x + f"-{index_name}"
            )
            entities_df["text_unit_ids"] = entities_df["text_unit_ids"].apply(
                lambda x: [i + f"-{index_name}" for i in x]
            )
            max_vals["entities"] = entities_df["human_readable_id"].max()
            entities_dfs.append(entities_df)

            relationships_df = get_df(relationships_table_path)
            for i in relationships_df["human_readable_id"].astype(int):
                links["relationships"][i + max_vals["relationships"] + 1] = {
                    "index_name": sanitized_index_names_link[index_name],
                    "id": i,
                }
            if max_vals["relationships"] != -1:
                col = (
                    relationships_df["human_readable_id"].astype(int)
                    + max_vals["relationships"]
                    + 1
                )
                relationships_df["human_readable_id"] = col.astype(str)
            relationships_df["source"] = relationships_df["source"].apply(
                lambda x: x + f"-{index_name}"
            )
            relationships_df["target"] = relationships_df["target"].apply(
                lambda x: x + f"-{index_name}"
            )
            relationships_df["text_unit_ids"] = relationships_df["text_unit_ids"].apply(
                lambda x: [i + f"-{index_name}" for i in x]
            )
            max_vals["relationships"] = (
                relationships_df["human_readable_id"].astype(int).max()
            )
            relationships_dfs.append(relationships_df)

            text_units_df = get_df(text_units_table_path)
            text_units_df["id"] = text_units_df["id"].apply(
                lambda x: f"{x}-{index_name}"
            )
            text_units_dfs.append(text_units_df)

            index_container_client = blob_service_client.get_container_client(
                index_name
            )
            if index_container_client.get_blob_client(COVARIATES_TABLE).exists():
                covariates_df = get_df(covariates_table_path)
                if i in covariates_df["human_readable_id"].astype(int):
                    links["covariates"][i + max_vals["covariates"] + 1] = {
                        "index_name": sanitized_index_names_link[index_name],
                        "id": i,
                    }
                if max_vals["covariates"] != -1:
                    col = (
                        covariates_df["human_readable_id"].astype(int)
                        + max_vals["covariates"]
                        + 1
                    )
                    covariates_df["human_readable_id"] = col.astype(str)
                max_vals["covariates"] = (
                    covariates_df["human_readable_id"].astype(int).max()
                )
                covariates_dfs.append(covariates_df)

        nodes_combined = pd.concat(nodes_dfs, axis=0, ignore_index=True)
        community_combined = pd.concat(community_dfs, axis=0, ignore_index=True)
        entities_combined = pd.concat(entities_dfs, axis=0, ignore_index=True)
        text_units_combined = pd.concat(text_units_dfs, axis=0, ignore_index=True)
        relationships_combined = pd.concat(relationships_dfs, axis=0, ignore_index=True)
        covariates_combined = (
            pd.concat(covariates_dfs, axis=0, ignore_index=True)
            if covariates_dfs != []
            else None
        )

        # load custom pipeline settings
        this_directory = os.path.dirname(
            os.path.abspath(inspect.getfile(inspect.currentframe()))
        )
        data = yaml.safe_load(open(f"{this_directory}/pipeline-settings.yaml"))
        # layer the custom settings on top of the default configuration settings of graphrag
        parameters = create_graphrag_config(data, ".")

        # add index_names to vector_store args
        parameters.embeddings.vector_store["index_names"] = sanitized_index_names
        # internally write over the get_embedding_description_store
        # method to use the multi-index collection.
        import graphrag.api.query

        graphrag.api.query._get_embedding_description_store = (
            _get_embedding_description_store
        )

        # perform streaming local search
        return StreamingResponse(
            _wrapper(
                local_search_streaming_internal(
                    config=parameters,
                    nodes=nodes_combined,
                    entities=entities_combined,
                    community_reports=community_combined,
                    text_units=text_units_combined,
                    relationships=relationships_combined,
                    covariates=covariates_combined,
                    community_level=COMMUNITY_LEVEL,
                    response_type="Multiple Paragraphs",
                    query=request.query,
                ),
                links,
            ),
            media_type="application/json",
        )
    except Exception as e:
        logger = load_pipeline_logger()
        logger.error(
            message="Error encountered while streaming local search response",
            cause=e,
            stack=traceback.format_exc(),
        )
        raise HTTPException(status_code=500, detail=None)


async def _wrapper(x, links):
    context = None
    async for i in x:
        if context:
            yield json.dumps({"token": i, "context": None}).encode("utf-8") + b"\n"
        else:
            context = i
    context = _update_context(context, links)
    context = json.dumps({"token": "<EOM>", "context": context}).encode("utf-8") + b"\n"
    yield context
