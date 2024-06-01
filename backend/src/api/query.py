# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import inspect
import os

import pandas as pd
import yaml
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from graphrag.config import create_graphrag_config

from src.api.azure_clients import BlobServiceClientSingleton
from src.api.common import (
    validate_index_file_exist,
    verify_subscription_key_exist,
)
from src.meta_agent.community.retrieve import CommunitySearchHelpers
from src.meta_agent.global_search.retrieve import GlobalSearchHelpers
from src.models import (
    GraphRequest,
    GraphResponse,
    PipelineJob,
)
from src.reporting import ReporterSingleton
from src.typing import PipelineJobState
from src.utils import query as query_helper

query_route = APIRouter(
    prefix="/query",
    tags=["Query Operations"],
)

if os.getenv("KUBERNETES_SERVICE_HOST"):
    query_route.dependencies.append(Depends(verify_subscription_key_exist))


@query_route.post(
    "/global",
    summary="Perform a global search across the knowledge graph index",
    description="The global query method generates answers by searching over all AI-generated community reports in a map-reduce fashion. This is a resource-intensive method, but often gives good responses for questions that require an understanding of the dataset as a whole.",
    response_model=GraphResponse,
    responses={200: {"model": GraphResponse}},
)
async def global_query(request: GraphRequest):
    # this is a slightly modified version of the graphrag.query.cli.run_global_search method
    if isinstance(request.index_name, str):
        index_names = [request.index_name]
    else:
        index_names = request.index_name

    for index_name in index_names:
        if not _is_index_complete(index_name):
            raise HTTPException(
                status_code=500,
                detail=f"{index_name} not ready for querying.",
            )

    ENTITY_TABLE = "output/create_final_nodes.parquet"
    COMMUNITY_REPORT_TABLE = "output/create_final_community_reports.parquet"

    for index_name in index_names:
        validate_index_file_exist(index_name, COMMUNITY_REPORT_TABLE)
        validate_index_file_exist(index_name, ENTITY_TABLE)

    # current investigations show that community level 1 is the most useful for global search
    COMMUNITY_LEVEL = 1
    try:
        report_dfs = []
        for index_name in index_names:
            entity_table_path = f"abfs://{index_name}/{ENTITY_TABLE}"
            community_report_table_path = (
                f"abfs://{index_name}/{COMMUNITY_REPORT_TABLE}"
            )
            report_df = query_helper.get_reports(
                entity_table_path, community_report_table_path, COMMUNITY_LEVEL
            )

            report_dfs.append(report_df)

        # overload title field to include index_name and index_id for provenance tracking
        report_df = report_dfs[0]
        max_id = 0
        if len(report_df["community_id"]) > 0:
            max_id = report_df["community_id"].astype(int).max()
        report_df["title"] = [
            index_names[0] + "<sep>" + i + "<sep>" + t
            for i, t in zip(report_df["community_id"], report_df["title"])
        ]
        for idx, df in enumerate(report_dfs[1:]):
            df["title"] = [
                index_names[idx + 1] + "<sep>" + i + "<sep>" + t
                for i, t in zip(df["community_id"], df["title"])
            ]
            df["community_id"] = [str(int(i) + max_id + 1) for i in df["community_id"]]
            report_df = pd.concat([report_df, df], ignore_index=True, sort=False)
            if len(report_df["community_id"]) > 0:
                max_id = report_df["community_id"].astype(int).max()

        # load custom pipeline settings
        this_directory = os.path.dirname(
            os.path.abspath(inspect.getfile(inspect.currentframe()))
        )
        data = yaml.safe_load(open(f"{this_directory}/pipeline_settings.yaml"))
        # layer the custom settings on top of the default configuration settings of graphrag
        parameters = create_graphrag_config(data, ".")

        # perform async search
        global_search = GlobalSearchHelpers(config=parameters)
        search_engine = global_search.get_search_engine(report_df=report_df)
        result = await search_engine.asearch(query=request.query)
        # reformat context data to match azure ai search output format
        result.context_data = _reformat_context_data(result.context_data)

        # map title into index_name, index_id and title for provenance tracking
        result.context_data["reports"] = [
            dict(
                {k: entry[k] for k in entry},
                **{
                    "index_name": entry["title"].split("<sep>")[0],
                    "index_id": entry["title"].split("<sep>")[1],
                    "title": entry["title"].split("<sep>")[2],
                },
            )
            for entry in result.context_data["reports"]
        ]

        return GraphResponse(result=result.response, context_data=result.context_data)
    except Exception as e:
        reporter = ReporterSingleton().get_instance()
        reporter.on_error(f"Could not perform global search. Exception: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@query_route.post(
    "/local",
    summary="Perform a local search across the knowledge graph index.",
    description="The local query method generates answers by combining relevant data from the AI-extracted knowledge-graph with text chunks of the raw documents. This method is suitable for questions that require an understanding of specific entities mentioned in the documents (e.g. What are the healing properties of chamomile?).",
    response_model=GraphResponse,
    responses={200: {"model": GraphResponse}},
)
async def local_query(request: GraphRequest):
    if isinstance(request.index_name, str):
        index_names = [request.index_name]
    else:
        index_names = request.index_name

    for index_name in index_names:
        if not _is_index_complete(index_name):
            raise HTTPException(
                status_code=500,
                detail=f"{index_name} not ready for querying.",
            )

    blob_service_client = BlobServiceClientSingleton.get_instance()
    report_dfs = []
    entity_dfs = []
    relationship_dfs = []
    covariate_dfs = []
    text_unit_dfs = []
    for index_idx, index_name in enumerate(index_names):
        add_on = "-" + str(index_idx)
        COMMUNITY_REPORT_TABLE = "output/create_final_community_reports.parquet"
        ENTITY_TABLE = "output/create_final_nodes.parquet"
        ENTITY_EMBEDDING_TABLE = "output/create_final_entities.parquet"
        RELATIONSHIP_TABLE = "output/create_final_relationships.parquet"
        COVARIATE_TABLE = "output/create_final_covariates.parquet"
        TEXT_UNIT_TABLE = "output/create_final_text_units.parquet"
        COMMUNITY_LEVEL = 2

        # check for existence of files the query relies on to validate the index is complete
        validate_index_file_exist(index_name, COMMUNITY_REPORT_TABLE)
        validate_index_file_exist(index_name, ENTITY_TABLE)
        validate_index_file_exist(index_name, ENTITY_EMBEDDING_TABLE)
        validate_index_file_exist(index_name, TEXT_UNIT_TABLE)

        # get entities
        entity_table_path = f"abfs://{index_name}/{ENTITY_TABLE}"
        entity_embedding_table_path = f"abfs://{index_name}/{ENTITY_EMBEDDING_TABLE}"
        entity_df = query_helper.get_entities(
            entity_table_path=entity_table_path,
            entity_embedding_table_path=entity_embedding_table_path,
            community_level=COMMUNITY_LEVEL,
        )
        entity_df.id = entity_df.id.apply(lambda x: x + add_on)
        entity_df.text_unit_ids = entity_df.text_unit_ids.apply(
            lambda x: [i + add_on for i in x]
        )
        entity_dfs.append(entity_df)

        # get relationships (the graph edges)
        relationship_df = query_helper.get_relationships(
            f"abfs://{index_name}/{RELATIONSHIP_TABLE}"
        )
        relationship_df.id = relationship_df.id.apply(lambda x: x + add_on)
        relationship_df.text_unit_ids = relationship_df.text_unit_ids.apply(
            lambda x: [i + add_on for i in x]
        )
        relationship_dfs.append(relationship_df)

        # get covariates, ie, claims about the entities
        # This step is not required, so only append if file exists
        index_container_client = blob_service_client.get_container_client(index_name)
        if index_container_client.get_blob_client(COVARIATE_TABLE).exists():
            covariate_df = query_helper.get_covariates(
                f"abfs://{index_name}/{COVARIATE_TABLE}"
            )
            covariate_df.short_id = covariate_df.short_id.astype(float).astype(int)
            covariate_df.id = covariate_df.id.apply(lambda x: x + add_on)
            covariate_df.document_ids = covariate_df.document_ids.apply(
                lambda x: [i + add_on for i in x]
            )
            covariate_dfs.append(covariate_df)

        # get community reports
        entity_table_path = f"abfs://{index_name}/{ENTITY_TABLE}"
        community_report_table_path = f"abfs://{index_name}/{COMMUNITY_REPORT_TABLE}"
        report_df = query_helper.get_reports(
            entity_table_path, community_report_table_path, COMMUNITY_LEVEL
        )
        report_df.id = report_df.id.apply(lambda x: x + add_on)
        report_dfs.append(report_df)

        # get text units
        text_unit_df = query_helper.get_text_units(
            f"abfs://{index_name}/{TEXT_UNIT_TABLE}"
        )
        text_unit_df.id = text_unit_df.id.apply(lambda x: x + add_on)
        text_unit_df.document_ids = text_unit_df.document_ids.apply(
            lambda x: [i + add_on for i in x]
        )
        text_unit_df.entity_ids = text_unit_df.entity_ids.apply(
            lambda x: [i + add_on for i in x]
        )
        text_unit_df.relationship_ids = text_unit_df.relationship_ids.apply(
            lambda x: [i + add_on for i in x]
        )
        text_unit_dfs.append(text_unit_df)

    # for each list of dataframes (report_dfs, entity_dfs, relationship_dfs, covariate_dfs, text_unit_dfs)
    # merge the associated data frames into a single dataframe (keeping track of index) to pass to the search engine
    report_df = report_dfs[0]
    max_id = 0
    if len(report_df["community_id"]) > 0:
        max_id = report_df["community_id"].astype(float).astype(int).max()
    report_df["title"] = [
        index_names[0] + "<sep>" + i + "<sep>" + str(t)
        for i, t in zip(report_df["community_id"], report_df["title"])
    ]
    for idx, df in enumerate(report_dfs[1:]):
        df["title"] = [
            index_names[idx + 1] + "<sep>" + str(i) + "<sep>" + str(t)
            for i, t in zip(df["community_id"], df["title"])
        ]
        df["community_id"] = [str(int(i) + max_id + 1) for i in df["community_id"]]
        report_df = pd.concat([report_df, df], ignore_index=True, sort=False)
        if len(report_df["community_id"]) > 0:
            max_id = report_df["community_id"].astype(float).astype(int).max()

    entity_df = entity_dfs[0]
    entity_df["description"] = [
        index_names[0] + "<sep>" + str(i) + "<sep>" + str(t)
        for i, t in zip(entity_df["short_id"], entity_df["description"])
    ]
    max_id = 0
    if len(entity_df["short_id"]) > 0:
        max_id = entity_df["short_id"].astype(float).astype(int).max()
    for idx, df in enumerate(entity_dfs[1:]):
        df["description"] = [
            index_names[idx + 1] + "<sep>" + str(i) + "<sep>" + str(t)
            for i, t in zip(df["short_id"], df["description"])
        ]
        df["short_id"] = [str(int(i) + max_id + 1) for i in range(len(df["short_id"]))]
        entity_df = pd.concat([entity_df, df], ignore_index=True, sort=False)
        if len(entity_df["short_id"]) > 0:
            max_id = entity_df["short_id"].astype(float).astype(int).max()

    relationship_df = relationship_dfs[0]
    relationship_df["description"] = [
        index_names[0] + "<sep>" + str(i) + "<sep>" + str(t)
        for i, t in zip(relationship_df["short_id"], relationship_df["description"])
    ]
    max_id = 0
    if len(relationship_df["short_id"]) > 0:
        max_id = relationship_df["short_id"].astype(float).astype(int).max()
    for idx, df in enumerate(relationship_dfs[1:]):
        df["description"] = [
            index_names[idx + 1] + "<sep>" + str(i) + "<sep>" + str(t)
            for i, t in zip(df["short_id"], df["description"])
        ]
        df["short_id"] = [str(int(i) + max_id + 1) for i in range(len(df["short_id"]))]
        relationship_df = pd.concat(
            [relationship_df, df], ignore_index=True, sort=False
        )
        if len(relationship_df["short_id"]) > 0:
            max_id = relationship_df["short_id"].astype(float).astype(int).max()

    if len(covariate_dfs) > 0:
        covariate_df = covariate_dfs[0]
        covariate_df["subject_id"] = [
            index_names[0] + "<sep>" + str(i) + "<sep>" + str(t)
            for i, t in zip(covariate_df["short_id"], covariate_df["subject_id"])
        ]
        max_id = 0
        if len(covariate_df["short_id"]) > 0:
            max_id = covariate_df["short_id"].astype(float).astype(int).max()
        for idx, df in enumerate(covariate_dfs[1:]):
            df["subject_id"] = [
                index_names[idx + 1] + "<sep>" + str(i) + "<sep>" + str(t)
                for i, t in zip(df["short_id"], df["subject_id"])
            ]
            df["short_id"] = [
                str(int(i) + max_id + 1) for i in range(len(df["short_id"]))
            ]
            covariate_df = pd.concat([covariate_df, df], ignore_index=True, sort=False)
            if len(covariate_df["short_id"]) > 0:
                max_id = covariate_df["short_id"].astype(float).astype(int).max()
    else:
        covariate_df = None

    text_unit_df = text_unit_dfs[0]
    text_unit_df["text"] = [
        index_names[0] + "<sep>" + str(i) + "<sep>" + str(t)
        for i, t in zip(text_unit_df["id"], text_unit_df["text"])
    ]
    for idx, df in enumerate(text_unit_dfs[1:]):
        df["text"] = [
            index_names[idx + 1] + "<sep>" + str(i) + "<sep>" + str(t)
            for i, t in zip(df["id"], df["text"])
        ]
        text_unit_df = pd.concat([text_unit_df, df], ignore_index=True, sort=False)

    # load custom pipeline settings
    this_directory = os.path.dirname(
        os.path.abspath(inspect.getfile(inspect.currentframe()))
    )
    data = yaml.safe_load(open(f"{this_directory}/pipeline_settings.yaml"))
    # layer the custom settings on top of the default configuration settings of graphrag
    parameters = create_graphrag_config(data, ".")

    # convert all the pandas dataframe artifacts into community objects
    local_search = CommunitySearchHelpers(index_names=index_names, config=parameters)
    community_data = local_search.read_community_info(
        report_df=report_df,
        entity_df=entity_df,
        edges_df=relationship_df,
        covariate_df=covariate_df,
        text_unit_df=text_unit_df,
    )

    # load search engine
    search_engine = local_search.get_search_engine(community_data)
    result = await search_engine.asearch(request.query)

    # post-process the search results, mapping the index_name,index_id to allow for provenance tracking

    # reformat context data
    result.context_data = _reformat_context_data(result.context_data)

    # map title into index_name, index_id and title for provenance tracking
    result.context_data["reports"] = [
        dict(
            {k: entry[k] for k in entry},
            **{
                "index_name": entry["title"].split("<sep>")[0],
                "index_id": entry["title"].split("<sep>")[1],
                "title": entry["title"].split("<sep>")[2],
            },
        )
        for entry in result.context_data["reports"]
    ]

    # map description into index_name, index_id and description for provenance tracking
    result.context_data["entities"] = [
        dict(
            {k: entry[k] for k in entry},
            **{
                "index_name": entry["description"].split("<sep>")[0],
                "index_id": entry["description"].split("<sep>")[1],
                "description": entry["description"].split("<sep>")[2],
            },
        )
        for entry in result.context_data["entities"]
    ]

    # map description into index_name, index_id and description for provenance tracking
    result.context_data["relationships"] = [
        dict(
            {k: entry[k] for k in entry},
            **{
                "index_name": entry["description"].split("<sep>")[0],
                "index_id": entry["description"].split("<sep>")[1],
                "description": entry["description"].split("<sep>")[2],
            },
        )
        for entry in result.context_data["relationships"]
    ]

    # map text into index_name, index_id and text for provenance tracking
    result.context_data["sources"] = [
        dict(
            {k: entry[k] for k in entry},
            **{
                "index_name": entry["text"].split("<sep>")[0],
                "index_id": entry["text"].split("<sep>")[1].split("-")[0],
                "text": entry["text"].split("<sep>")[2],
            },
        )
        for entry in result.context_data["sources"]
    ]
    return GraphResponse(result=result.response, context_data=result.context_data)


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


def _reformat_context_data(context_data: dict) -> dict:
    """
    Reformats context_data for all query types. Reformats
    a dictionary of dictionaries into a dictionary of lists.
    One list entry for each record.  Records are grouped by
    original dictionary keys.

    Note: depending on which query type is used, the context_data may not contain all keys. In this case, the default behavior will be to set these keys as empty lists in order to preserve a standard output format for end users.
    """
    final_format = {"reports": [], "entities": [], "relationships": [], "claims": []}
    for key in context_data:
        try:
            records = context_data[key].to_dict(orient="records")
            if len(records) < 1:
                continue
            # sort records by threat rating
            if "rating" in records[0]:
                records = sorted(records, key=lambda x: x["rating"], reverse=True)
            final_format[key] = records
        except Exception:
            raise
    return final_format
