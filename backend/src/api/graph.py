# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from fastapi import (
    APIRouter,
    HTTPException,
)
from fastapi.responses import StreamingResponse

from src.logger.load_logger import load_pipeline_logger
from src.utils.azure_clients import AzureClientManager
from src.utils.common import (
    sanitize_name,
    validate_index_file_exist,
)

graph_route = APIRouter(
    prefix="/graph",
    tags=["Graph Operations"],
)


@graph_route.get(
    "/graphml/{index_name}",
    summary="Retrieve a GraphML file of the knowledge graph",
    response_description="GraphML file successfully downloaded",
)
async def get_graphml_file(index_name: str):
    # validate index_name and graphml file existence
    azure_client_manager = AzureClientManager()
    sanitized_index_name = sanitize_name(index_name)
    graphml_filename = "graph.graphml"
    blob_filepath = f"output/{graphml_filename}"  # expected file location of the graph based on the workflow
    validate_index_file_exist(sanitized_index_name, blob_filepath)
    try:
        blob_client = azure_client_manager.get_blob_service_client().get_blob_client(
            container=sanitized_index_name, blob=blob_filepath
        )
        blob_stream = blob_client.download_blob().chunks()
        return StreamingResponse(
            blob_stream,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={graphml_filename}"},
        )
    except Exception:
        logger = load_pipeline_logger()
        logger.error("Could not retrieve graphml file")
        raise HTTPException(
            status_code=500,
            detail=f"Could not retrieve graphml file for index '{index_name}'.",
        )
