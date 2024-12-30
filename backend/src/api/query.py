# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import inspect
import json
import os
import traceback
from typing import Any

import pandas as pd
import yaml
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from fastapi import (
    APIRouter,
    HTTPException,
)
from graphrag.config import create_graphrag_config
from graphrag.model.types import TextEmbedder
from graphrag.query.api import global_search, local_search
from graphrag.vector_stores.base import (
    BaseVectorStore,
    VectorStoreDocument,
    VectorStoreSearchResult,
)

from src.api.azure_clients import AzureClientManager
from src.api.common import (
    sanitize_name,
    validate_index_file_exist,
)
from src.logger import LoggerSingleton
from src.models import (
    GraphRequest,
    GraphResponse,
)
from src.typing.pipeline import PipelineJobState
from src.utils import query as query_helper
from src.utils.pipeline import PipelineJob

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
                detail=f"{index_name} not ready for querying.",
            )

    COMMUNITY_REPORT_TABLE = "output/create_final_community_reports.parquet"
    ENTITIES_TABLE = "output/create_final_entities.parquet"
    NODES_TABLE = "output/create_final_nodes.parquet"

    for index_name in sanitized_index_names:
        validate_index_file_exist(index_name, COMMUNITY_REPORT_TABLE)
        validate_index_file_exist(index_name, ENTITIES_TABLE)
        validate_index_file_exist(index_name, NODES_TABLE)

    if isinstance(request.community_level, int):
        COMMUNITY_LEVEL = request.community_level
    else:
        # Current investigations show that community level 1 is the most useful for global search. Set this as the default value
        COMMUNITY_LEVEL = 1

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

            # read the parquet files into DataFrames and add provenance information
            # note that nodes need to be set before communities so that max community id makes sense
            nodes_df = query_helper.get_df(nodes_table_path)
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

            community_df = query_helper.get_df(community_report_table_path)
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

            entities_df = query_helper.get_df(entities_table_path)
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

        # perform async search
        result = await global_search(
            config=parameters,
            nodes=nodes_combined,
            entities=entities_combined,
            community_reports=community_combined,
            community_level=COMMUNITY_LEVEL,
            response_type="Multiple Paragraphs",
            query=request.query,
        )

        # link index provenance to the context data
        context_data = _update_context(result[1], links)

        return GraphResponse(result=result[0], context_data=context_data)
    except Exception as e:
        logger = LoggerSingleton().get_instance()
        logger.on_error(
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
                detail=f"{index_name} not ready for querying.",
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

    for index_name in sanitized_index_names:
        # check for existence of files the query relies on to validate the index is complete
        validate_index_file_exist(index_name, COMMUNITY_REPORT_TABLE)
        validate_index_file_exist(index_name, ENTITIES_TABLE)
        validate_index_file_exist(index_name, NODES_TABLE)
        validate_index_file_exist(index_name, RELATIONSHIPS_TABLE)
        validate_index_file_exist(index_name, TEXT_UNITS_TABLE)

        community_report_table_path = f"abfs://{index_name}/{COMMUNITY_REPORT_TABLE}"
        covariates_table_path = f"abfs://{index_name}/{COVARIATES_TABLE}"
        entities_table_path = f"abfs://{index_name}/{ENTITIES_TABLE}"
        nodes_table_path = f"abfs://{index_name}/{NODES_TABLE}"
        relationships_table_path = f"abfs://{index_name}/{RELATIONSHIPS_TABLE}"
        text_units_table_path = f"abfs://{index_name}/{TEXT_UNITS_TABLE}"

        # read the parquet files into DataFrames and add provenance information

        # note that nodes need to set before communities to that max community id makes sense
        nodes_df = query_helper.get_df(nodes_table_path)
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

        community_df = query_helper.get_df(community_report_table_path)
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

        entities_df = query_helper.get_df(entities_table_path)
        for i in entities_df["human_readable_id"]:
            links["entities"][i + max_vals["entities"] + 1] = {
                "index_name": sanitized_index_names_link[index_name],
                "id": i,
            }
        if max_vals["entities"] != -1:
            entities_df["human_readable_id"] += max_vals["entities"] + 1
        entities_df["id"] = entities_df["id"].apply(lambda x: x + f"-{index_name}")
        entities_df["name"] = entities_df["name"].apply(lambda x: x + f"-{index_name}")
        entities_df["text_unit_ids"] = entities_df["text_unit_ids"].apply(
            lambda x: [i + f"-{index_name}" for i in x]
        )
        max_vals["entities"] = entities_df["human_readable_id"].max()
        entities_dfs.append(entities_df)

        relationships_df = query_helper.get_df(relationships_table_path)
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

        text_units_df = query_helper.get_df(text_units_table_path)
        text_units_df["id"] = text_units_df["id"].apply(lambda x: f"{x}-{index_name}")
        text_units_dfs.append(text_units_df)

        index_container_client = blob_service_client.get_container_client(index_name)
        if index_container_client.get_blob_client(COVARIATES_TABLE).exists():
            covariates_df = query_helper.get_df(covariates_table_path)
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
    import graphrag.query.api

    graphrag.query.api._get_embedding_description_store = (
        _get_embedding_description_store
    )
    # perform async search
    result = await local_search(
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
    )

    # link index provenance to the context data
    context_data = _update_context(result[1], links)

    return GraphResponse(result=result[0], context_data=context_data)


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


def _update_context(context, links):
    """
    Update context data.
    context_keys = ['reports', 'entities', 'relationships', 'claims', 'sources']
    """
    updated_context = {}
    for key in context:
        updated_entry = []
        if key == "reports":
            updated_entry = [
                dict(
                    {k: entry[k] for k in entry},
                    **{
                        "index_name": links["community"][int(entry["id"])][
                            "index_name"
                        ],
                        "index_id": links["community"][int(entry["id"])]["id"],
                    },
                )
                for entry in context[key]
            ]
        if key == "entities":
            updated_entry = [
                dict(
                    {k: entry[k] for k in entry},
                    **{
                        "entity": entry["entity"].split("-")[0],
                        "index_name": links["entities"][int(entry["id"])]["index_name"],
                        "index_id": links["entities"][int(entry["id"])]["id"],
                    },
                )
                for entry in context[key]
            ]
        if key == "relationships":
            updated_entry = [
                dict(
                    {k: entry[k] for k in entry},
                    **{
                        "source": entry["source"].split("-")[0],
                        "target": entry["target"].split("-")[0],
                        "index_name": links["relationships"][int(entry["id"])][
                            "index_name"
                        ],
                        "index_id": links["relationships"][int(entry["id"])]["id"],
                    },
                )
                for entry in context[key]
            ]
        if key == "claims":
            updated_entry = [
                dict(
                    {k: entry[k] for k in entry},
                    **{
                        "index_name": links["claims"][int(entry["id"])]["index_name"],
                        "index_id": links["claims"][int(entry["id"])]["id"],
                    },
                )
                for entry in context[key]
            ]
        if key == "sources":
            updated_entry = context[key]
        updated_context[key] = updated_entry
    return updated_context


def _get_embedding_description_store(
    entities: Any,
    vector_store_type: str = Any,
    config_args: dict | None = None,
):
    collection_names = [
        f"{index_name}_description_embedding"
        for index_name in config_args.get("index_names", [])
    ]
    ai_search_url = os.environ["AI_SEARCH_URL"]
    description_embedding_store = MultiAzureAISearch(
        collection_name="multi",
        document_collection=None,
        db_connection=None,
    )
    description_embedding_store.connect(url=ai_search_url)
    for collection_name in collection_names:
        description_embedding_store.add_collection(collection_name)
    return description_embedding_store


class MultiAzureAISearch(BaseVectorStore):
    """The Azure AI Search vector storage implementation."""

    def __init__(
        self,
        collection_name: str,
        db_connection: Any,
        document_collection: Any,
        query_filter: Any | None = None,
        **kwargs: Any,
    ):
        self.collection_name = collection_name
        self.db_connection = db_connection
        self.document_collection = document_collection
        self.query_filter = query_filter
        self.kwargs = kwargs
        self.collections = []

    def add_collection(self, collection_name: str):
        self.collections.append(collection_name)

    def connect(self, **kwargs: Any) -> Any:
        """Connect to the AzureAI vector store."""
        self.url = kwargs.get("url", None)
        self.vector_size = kwargs.get("vector_size", 1536)

        self.vector_search_profile_name = kwargs.get(
            "vector_search_profile_name", "vectorSearchProfile"
        )

        if self.url:
            pass
        else:
            not_supported_error = (
                "Azure AI Search client is not supported on local host."
            )
            raise ValueError(not_supported_error)

    def load_documents(
        self, documents: list[VectorStoreDocument], overwrite: bool = True
    ) -> None:
        raise NotImplementedError("load_documents() method not implemented")

    def filter_by_id(self, include_ids: list[str] | list[int]) -> Any:
        """Build a query filter to filter documents by a list of ids."""
        if include_ids is None or len(include_ids) == 0:
            self.query_filter = None
            # returning to keep consistency with other methods, but not needed
            return self.query_filter

        # more info about odata filtering here: https://learn.microsoft.com/en-us/azure/search/search-query-odata-search-in-function
        # search.in is faster that joined and/or conditions
        id_filter = ",".join([f"{id!s}" for id in include_ids])
        self.query_filter = f"search.in(id, '{id_filter}', ',')"

        # returning to keep consistency with other methods, but not needed
        # TODO: Refactor on a future PR
        return self.query_filter

    def similarity_search_by_vector(
        self, query_embedding: list[float], k: int = 10, **kwargs: Any
    ) -> list[VectorStoreSearchResult]:
        """Perform a vector-based similarity search."""
        vectorized_query = VectorizedQuery(
            vector=query_embedding, k_nearest_neighbors=k, fields="vector"
        )

        docs = []
        for collection_name in self.collections:
            add_on = "-" + str(collection_name.split("_")[0])
            audience = os.environ["AI_SEARCH_AUDIENCE"]
            db_connection = SearchClient(
                self.url,
                collection_name,
                DefaultAzureCredential(),
                audience=audience,
            )
            response = db_connection.search(
                vector_queries=[vectorized_query],
            )
            mod_response = []
            for r in response:
                r["id"] = r.get("id", "") + add_on
                mod_response += [r]
            docs += mod_response
        return [
            VectorStoreSearchResult(
                document=VectorStoreDocument(
                    id=doc.get("id", ""),
                    text=doc.get("text", ""),
                    vector=doc.get("vector", []),
                    attributes=(json.loads(doc.get("attributes", "{}"))),
                ),
                score=abs(doc["@search.score"]),
            )
            for doc in docs
        ]

    def similarity_search_by_text(
        self, text: str, text_embedder: TextEmbedder, k: int = 10, **kwargs: Any
    ) -> list[VectorStoreSearchResult]:
        """Perform a text-based similarity search."""
        query_embedding = text_embedder(text)
        if query_embedding:
            return self.similarity_search_by_vector(
                query_embedding=query_embedding, k=k
            )
        return []
