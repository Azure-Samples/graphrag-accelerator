# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import traceback
from io import BytesIO

import networkx as nx
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from fastapi.responses import StreamingResponse

from graphrag_app.logger.load_logger import load_pipeline_logger
from graphrag_app.typing.models import GraphDataResponse
from graphrag_app.utils.azure_clients import AzureClientManager
from graphrag_app.utils.common import (
    sanitize_name,
    subscription_key_check,
    validate_index_file_exist,
)

graph_route = APIRouter(
    prefix="/graph",
    tags=["Graph Operations"],
)
if os.getenv("KUBERNETES_SERVICE_HOST"):
    graph_route.dependencies.append(Depends(subscription_key_check))


@graph_route.get(
    "/graphml/{container_name}",
    summary="Retrieve a GraphML file of the knowledge graph",
    response_description="GraphML file successfully downloaded",
    status_code=status.HTTP_200_OK,
)
async def get_graphml_file(
    container_name, sanitized_container_name: str = Depends(sanitize_name)
):
    logger = load_pipeline_logger()

    # validate graphml file existence
    azure_client_manager = AzureClientManager()
    graphml_filename = "graph.graphml"
    blob_filepath = f"output/{graphml_filename}"  # expected file location of the graph based on the workflow
    validate_index_file_exist(sanitized_container_name, blob_filepath)
    try:
        blob_client = azure_client_manager.get_blob_service_client().get_blob_client(
            container=sanitized_container_name, blob=blob_filepath
        )
        blob_stream = blob_client.download_blob().chunks()
        return StreamingResponse(
            blob_stream,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename={graphml_filename}",
                "filename": graphml_filename,
            },
        )
    except Exception as e:
        logger.error(
            message="Could not fetch graphml file",
            cause=e,
            stack=traceback.format_exc(),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Could not fetch graphml file for '{container_name}'.",
        )
    

@graph_route.get(
    "/stats/{index_name}",
    summary="Retrieve basic graph statistics, number of nodes and edges",
    response_model=GraphDataResponse,
    responses={200: {"model": GraphDataResponse}},
    response_description="Retrieve the number of nodes and edges from the index graph",
)
async def retrieve_graph_stats(index_name: str):
    logger = load_pipeline_logger()

    # validate index_name and graphml file existence
    sanitized_index_name = sanitize_name(index_name)
    graphml_filename = "graph.graphml"
    graphml_filepath = f"output/{graphml_filename}"  # expected file location of the graph based on the workflow
    validate_index_file_exist(sanitized_index_name, graphml_filepath)

    try:
        azure_client_manager = AzureClientManager()
        storage_client = azure_client_manager.get_blob_service_client().get_blob_client(
            container=sanitized_index_name, blob=graphml_filepath
        )
        blob_data = storage_client.download_blob().readall()
        bytes_io = BytesIO(blob_data)
        g = nx.read_graphml(bytes_io)
        return GraphDataResponse(nodes=len(g.nodes), edges=len(g.edges))
    except Exception:
        logger.error("Could not retrieve graph data file")
        raise HTTPException(
            status_code=500,
            detail=f"Could not retrieve graph statistics for index '{index_name}'.",
        )
