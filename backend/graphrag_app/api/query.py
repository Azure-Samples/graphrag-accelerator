# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import traceback

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from graphrag.api.query import drift_search as graphrag_drift_search
from graphrag.api.query import global_search as graphrag_global_search
from graphrag.api.query import local_search as graphrag_local_search

from graphrag_app.logger.load_logger import load_pipeline_logger
from graphrag_app.typing.models import (
    GraphGlobalRequest,
    GraphRequest,
    GraphResponse,
)
from graphrag_app.typing.pipeline import PipelineJobState
from graphrag_app.utils.common import (
    get_data_tables,
    sanitize_name,
    subscription_key_check,
    update_multi_index_context_data,
)
from graphrag_app.utils.pipeline import PipelineJob

query_route = APIRouter(
    prefix="/query",
    tags=["Query Operations"],
)
if os.getenv("KUBERNETES_SERVICE_HOST"):
    query_route.dependencies.append(Depends(subscription_key_check))


@query_route.post(
    "/global",
    summary="Perform a global search across the knowledge graph index",
    description="The global query method generates answers by searching over all AI-generated community reports in a map-reduce fashion. This is a resource-intensive method, but often gives good responses for questions that require an understanding of the dataset as a whole.",
    response_model=GraphResponse,
    responses={status.HTTP_200_OK: {"model": GraphResponse}},
)
async def global_search(request: GraphGlobalRequest):
    logger = load_pipeline_logger()
    
    if isinstance(request.index_name, list):
        raise HTTPException(
                status_code=501,
                detail="Multi-index query is not implemented.",
            )
    
    # make sure all referenced indexes have completed
    index_name_map = {
        "index_name": request.index_name,
        "sanitized_name": sanitize_name(request.index_name),
    }
    if not _is_index_complete(index_name_map['sanitized_name']):
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail=f"{index_name} not ready for querying.",
        )

    try:
        data_tables = get_data_tables(
            index_name_map,
            community_level=request.community_level,
            include_local_context=False
        )

        # perform async search
        result = await graphrag_global_search(
            config=data_tables.config,
            communities=data_tables.communities,
            entities=data_tables.entities,
            community_reports=data_tables.community_reports,
            community_level=data_tables.community_level,
            dynamic_community_selection=request.dynamic_community_selection,
            response_type=request.response_type,
            query=request.query,
        )
        context = update_multi_index_context_data(
            result[1], 
            index_name=index_name_map['index_name'],
            index_id=index_name_map['sanitized_name']
        )

        return GraphResponse(result=result[0], context_data=context)
    except Exception as e:
        logger.error(
            message="Could not perform global search.",
            cause=e,
            stack=traceback.format_exc()
        )
        raise HTTPException(status_code=500, detail=None)


@query_route.post(
    "/local",
    summary="Perform a local search across the knowledge graph index.",
    description="The local query method generates answers by combining relevant data from the AI-extracted knowledge-graph with text chunks of the raw documents. This method is suitable for questions that require an understanding of specific entities mentioned in the documents (e.g. What are the healing properties of chamomile?).",
    response_model=GraphResponse,
    responses={status.HTTP_200_OK: {"model": GraphResponse}},
)
async def local_search(request: GraphRequest):
    logger = load_pipeline_logger()
    
    if isinstance(request.index_name, list):
        raise HTTPException(
                status_code=501,
                detail="Multi-index query is not implemented.",
            )
    
    # make sure all referenced indexes have completed
    index_name_map = {
        "index_name": request.index_name,
        "sanitized_name": sanitize_name(request.index_name),
    }
    if not _is_index_complete(index_name_map['sanitized_name']):
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail=f"{index_name} not ready for querying.",
        )

    try:
        data_tables = get_data_tables(
            index_name_map,
            community_level=request.community_level,
            include_local_context=True
        )
        
        # perform async search
        result = await graphrag_local_search(
            config=data_tables.config,
            entities=data_tables.entities,
            community_reports=data_tables.community_reports,
            communities=data_tables.communities,
            text_units=data_tables.text_units,
            relationships=data_tables.relationships,
            covariates=data_tables.covariates,
            community_level=data_tables.community_level,
            response_type=request.response_type,
            query=request.query,
        )
        context = update_multi_index_context_data(
            result[1], 
            index_name=index_name_map['index_name'],
            index_id=index_name_map['sanitized_name']
        )

        return GraphResponse(result=result[0], context_data=context)
    except Exception as e:
        logger.error(
            message="Could not perform local search.",
            cause=e,
            stack=traceback.format_exc()
        )
        raise HTTPException(status_code=500, detail=None)


@query_route.post(
    "/drift",
    summary="Perform a drift (Dynamic Reasoning and Inference with Flexible Traversal) search across the knowledge graph index",
    description="DRIFT search offers a new approach to local search queries by incorporating community information, greatly expanding the range of facts retrieved for the final answer. This approach extends the GraphRAG query engine by adding a more comprehensive local search option that leverages community insights to refine queries into detailed follow-up questions. While resource-intensive, DRIFT search typically delivers the most accurate responses for queries that demand both a broad understanding of the entire dataset and deeper semantic knowledge about specific details.",
    response_model=GraphResponse,
    responses={200: {"model": GraphResponse}},
)
async def drift_search(request: GraphRequest):
    logger = load_pipeline_logger()
    
    if isinstance(request.index_name, list):
        raise HTTPException(
                status_code=501,
                detail="Multi-index query is not implemented.",
            )
    
    # make sure all referenced indexes have completed
    index_name_map = {
        "index_name": request.index_name,
        "sanitized_name": sanitize_name(request.index_name),
    }
    if not _is_index_complete(index_name_map['sanitized_name']):
        raise HTTPException(
            status_code=500,
            detail=f"{index_name_map['index_name']} not ready for querying.",
        )

    try:
        data_tables = get_data_tables(
            index_name_map,
            community_level=request.community_level,
            include_local_context=True
        )
        
        # perform async search
        result = await graphrag_drift_search(
            config=data_tables.config,
            entities=data_tables.entities,
            community_reports=data_tables.community_reports,
            communities=data_tables.communities,
            text_units=data_tables.text_units,
            relationships=data_tables.relationships,
            community_level=data_tables.community_level,
            response_type=request.response_type,
            query=request.query,
        )
        context = update_multi_index_context_data(
            result[1], 
            index_name=index_name_map['index_name'],
            index_id=index_name_map['sanitized_name']
        )

        return GraphResponse(result=result[0], context_data=context)
    except Exception as e:
        logger.error(
            message="Could not perform drift search.",
            cause=e,
            stack=traceback.format_exc()
        )
        raise HTTPException(status_code=500, detail=None)


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