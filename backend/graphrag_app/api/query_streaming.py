# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
import os
import traceback

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from fastapi.responses import StreamingResponse
from graphrag.api.query import (
    drift_search_streaming as graphrag_drift_search_streaming,
)
from graphrag.api.query import (
    global_search_streaming as graphrag_global_search_streaming,
)
from graphrag.api.query import (
    local_search_streaming as graphrag_local_search_streaming,
)

from graphrag_app.api.query import _is_index_complete
from graphrag_app.logger.load_logger import load_pipeline_logger
from graphrag_app.typing.models import (
    GraphDriftRequest,
    GraphGlobalRequest,
    GraphLocalRequest,
    StreamingCallback,
)
from graphrag_app.utils.common import (
    get_data_tables,
    sanitize_name,
    subscription_key_check,
    update_multi_index_context_data,
)

query_streaming_route = APIRouter(
    prefix="/query/streaming",
    tags=["Query Streaming Operations"],
)
if os.getenv("KUBERNETES_SERVICE_HOST"):
    query_streaming_route.dependencies.append(Depends(subscription_key_check))


@query_streaming_route.post(
    "/global",
    summary="Stream a response back after performing a global search",
    description="The global query method generates answers by searching over all AI-generated community reports in a map-reduce fashion. This is a resource-intensive method, but often gives good responses for questions that require an understanding of the dataset as a whole.",
    status_code=status.HTTP_200_OK,
)
async def global_search_streaming(request: GraphGlobalRequest):
    logger = load_pipeline_logger()
    try:
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
            
        data_tables = get_data_tables(
            index_name_map,
            community_level=request.community_level,
            include_local_context=False
        )
        query_callback = StreamingCallback()
        return StreamingResponse(
            _streaming_wrapper(
                graphrag_global_search_streaming(
                    config=data_tables.config,
                    entities=data_tables.entities,
                    communities=data_tables.communities,
                    community_reports=data_tables.community_reports,
                    community_level=data_tables.community_level,
                    dynamic_community_selection=request.dynamic_community_selection,
                    response_type=request.response_type,
                    query=request.query,
                    callbacks=[query_callback]
                ),
                index_name=index_name_map["index_name"],
                index_id=index_name_map["sanitized_name"],
                query_callback=query_callback
            ),
            media_type="application/json",
        )
    except Exception as e:
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
    status_code=status.HTTP_200_OK,
)
async def local_search_streaming(request: GraphLocalRequest):
    logger = load_pipeline_logger()
    try:
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
        
        data_tables = get_data_tables(
            index_name_map,
            community_level=request.community_level,
            include_local_context=True
        )
        query_callback = StreamingCallback()
        return StreamingResponse(
            _streaming_wrapper(
                graphrag_local_search_streaming(
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
                    callbacks=[query_callback]
                ),
                index_name=index_name_map["index_name"],
                index_id=index_name_map["sanitized_name"],
                query_callback=query_callback
            ),
            media_type="application/json",
        )
    except Exception as e:
        logger.error(
            message="Error encountered while streaming local search response",
            cause=e,
            stack=traceback.format_exc(),
        )
        raise HTTPException(status_code=500, detail=None)


@query_streaming_route.post(
    "/drift",
    summary="Perform a drift (Dynamic Reasoning and Inference with Flexible Traversal) search across the knowledge graph index",
    description="DRIFT search offers a new approach to local search queries by incorporating community information, greatly expanding the range of facts retrieved for the final answer. This approach extends the GraphRAG query engine by adding a more comprehensive local search option that leverages community insights to refine queries into detailed follow-up questions. While resource-intensive, DRIFT search typically delivers the most accurate responses for queries that demand both a broad understanding of the entire dataset and deeper semantic knowledge about specific details.",
)
async def drift_search_streaming(request: GraphDriftRequest):
    logger = load_pipeline_logger()
    try:
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
        
        data_tables = get_data_tables(
            index_name_map,
            community_level=request.community_level,
            include_local_context=True
        )
        query_callback = StreamingCallback()
        return StreamingResponse(
            _streaming_wrapper(
                graphrag_drift_search_streaming(
                    config=data_tables.config,
                    entities=data_tables.entities,
                    community_reports=data_tables.community_reports,
                    communities=data_tables.communities,
                    text_units=data_tables.text_units,
                    relationships=data_tables.relationships,
                    community_level=data_tables.community_level,
                    response_type=request.response_type,
                    query=request.query,
                    callbacks=[query_callback]
                ),
                index_name=index_name_map["index_name"],
                index_id=index_name_map["sanitized_name"],
                query_callback=query_callback
            ),
            media_type="application/json",
        )
    except Exception as e:
        logger.error(
            message="Error encountered while streaming drift search response",
            cause=e,
            stack=traceback.format_exc(),
        )
        raise HTTPException(status_code=500, detail=None)


async def _streaming_wrapper(token_iter, index_name: str, index_id: str, query_callback: StreamingCallback):
    async for token in token_iter:
        yield json.dumps(
            {
                "token": token, 
                "context": None
            }
        ).encode("utf-8") + b"\n"
    yield json.dumps(
        {
            "token": "<EOM>",
            "context": update_multi_index_context_data(query_callback.context, index_name, index_id)
        }
    ).encode("utf-8") + b"\n"
    