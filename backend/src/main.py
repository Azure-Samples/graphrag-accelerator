# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import traceback

from fastapi import (
    Depends,
    FastAPI,
    Request,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.ext.fastapi.fastapi_middleware import FastAPIMiddleware
from opencensus.trace.samplers import ProbabilitySampler

from src.api.common import verify_subscription_key_exist
from src.api.data import data_route
from src.api.experimental import experimental_route
from src.api.graph import graph_route
from src.api.index import index_route
from src.api.index_configuration import index_configuration_route
from src.api.query import query_route
from src.api.source import source_route
from src.reporting import ReporterSingleton

url = os.getenv("APIM_GATEWAY_URL", "localhost")
version = os.getenv("GRAPHRAG_VERSION", "undefined_version")

app = FastAPI(
    docs_url="/manpage/docs",
    openapi_url="/manpage/openapi.json",
    title="GraphRAG",
    version=version,
)


async def catch_all_exceptions_middleware(request: Request, call_next):
    """a function to globally catch all exceptions and return a 500 response with the exception message"""
    try:
        return await call_next(request)
    except Exception as e:
        reporter = ReporterSingleton().get_instance()
        reporter.on_error(
            message="Unexpected internal server error",
            cause=e,
            stack=traceback.format_exc(),
        )
        return Response("Unexpected internal server error.", status_code=500)


app.middleware("http")(catch_all_exceptions_middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# exporter = AzureExporter(connection_string=os.environ["APP_INSIGHTS_CONNECTION_STRING"])
# sampler = ProbabilitySampler(1.0)
# app.add_middleware(FastAPIMiddleware)


app.include_router(data_route)
app.include_router(index_route)
app.include_router(query_route)
app.include_router(index_configuration_route)
app.include_router(source_route)
app.include_router(graph_route)
app.include_router(experimental_route)


# health check endpoint
@app.get(
    "/health",
    summary="API health check",
    dependencies=[Depends(verify_subscription_key_exist)]
    if os.getenv("KUBERNETES_SERVICE_HOST")
    else None,
)
def health_check():
    """Returns a 200 response to indicate the API is healthy."""
    return Response(status_code=status.HTTP_200_OK)
