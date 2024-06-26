# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
from io import BytesIO

import networkx as nx
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from fastapi.responses import StreamingResponse

from src.api.azure_clients import BlobServiceClientSingleton
from src.api.common import (
    sanitize_name,
    validate_index_file_exist,
    verify_subscription_key_exist,
)
from src.models import GraphDataResponse
from src.reporting import ReporterSingleton

blob_service_client = BlobServiceClientSingleton.get_instance()


graph_route = APIRouter(
    prefix="/graph",
    tags=["Graph Operations"],
)

if os.getenv("KUBERNETES_SERVICE_HOST"):
    graph_route.dependencies.append(Depends(verify_subscription_key_exist))


@graph_route.get(
    "/graphml/{index_name}",
    summary="Retrieve a GraphML file of the knowledge graph",
    response_description="GraphML file successfully downloaded",
)
async def retrieve_graphml_file(index_name: str):
    # validate index_name and graphml file existence
    sanitized_index_name = sanitize_name(index_name)
    graphml_filename = "summarized_graph.graphml"
    blob_filepath = f"output/{graphml_filename}"  # expected file location of the graph based on the workflow
    validate_index_file_exist(sanitized_index_name, blob_filepath)
    try:
        blob_client = blob_service_client.get_blob_client(
            container=sanitized_index_name, blob=blob_filepath
        )
        blob_stream = blob_client.download_blob().chunks()
        return StreamingResponse(
            blob_stream,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={graphml_filename}"},
        )
    except Exception as e:
        reporter = ReporterSingleton().get_instance()
        reporter.on_error(f"Could not retrieve graphml file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Could not retrieve graphml file for index '{index_name}'.",
        )


@graph_route.get(
    "/stats/{index_name}",
    summary="Retrieve basic graph statistics, number of nodes and edges",
    response_model=GraphDataResponse,
    responses={200: {"model": GraphDataResponse}},
)
async def retrieve_graph_stats(index_name: str):
    # validate index_name and knowledge graph file existence
    sanitized_index_name = sanitize_name(index_name)
    graph_file = "output/summarized_graph.graphml"  # expected filename of the graph based on the indexing workflow
    validate_index_file_exist(sanitized_index_name, graph_file)
    try:
        storage_client = blob_service_client.get_container_client(sanitized_index_name)
        blob_data = storage_client.download_blob(graph_file).readall()
        bytes_io = BytesIO(blob_data)
        g = nx.read_graphml(bytes_io)
        return GraphDataResponse(nodes=len(g.nodes), edges=len(g.edges))
    except Exception as e:
        reporter = ReporterSingleton().get_instance()
        reporter.on_error(f"Could not retrieve graph data file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Could not retrieve graph statistics for index '{index_name}'.",
        )
