# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import traceback

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from fastapi.responses import StreamingResponse

from graphrag_app.logger.load_logger import load_pipeline_logger
from graphrag_app.utils.azure_clients import AzureClientManager
from graphrag_app.utils.common import (
    sanitize_name,
    validate_index_file_exist,
)

graph_route = APIRouter(
    prefix="/graph",
    tags=["Graph Operations"],
)


@graph_route.get(
    "/graphml/{container_name}",
    summary="Retrieve a GraphML file of the knowledge graph",
    response_description="GraphML file successfully downloaded",
)
async def get_graphml_file(
    container_name, sanitized_container_name: str = Depends(sanitize_name)
):
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
            headers={"Content-Disposition": f"attachment; filename={graphml_filename}"},
        )
    except Exception as e:
        logger = load_pipeline_logger()
        logger.error(
            message="Could not fetch graphml file",
            cause=e,
            stack=traceback.format_exc(),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Could not fetch graphml file for '{container_name}'.",
        )
