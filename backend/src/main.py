# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import traceback
from contextlib import asynccontextmanager

import yaml
from fastapi import (
    Depends,
    FastAPI,
    Request,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from kubernetes import (
    client,
    config,
)

from src.api.common import verify_subscription_key_exist
from src.api.data import data_route
from src.api.experimental import experimental_route
from src.api.graph import graph_route
from src.api.index import index_route
from src.api.index_configuration import index_configuration_route
from src.api.query import query_route
from src.api.source import source_route
from src.reporting import ReporterSingleton


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


# deploy a cronjob to manage indexing jobs
@asynccontextmanager
async def lifespan(app: FastAPI):
    # This function is called when the FastAPI application first starts up.
    # To manage multiple graphrag indexing jobs, we deploy a k8s cronjob.
    # This cronjob will act as a job manager that creates/manages the execution of graphrag indexing jobs as they are requested.
    try:
        # Check if the cronjob exists and create it if it does not exist
        config.load_incluster_config()
        # retrieve the running pod spec
        core_v1 = client.CoreV1Api()
        pod_name = os.environ["HOSTNAME"]
        pod = core_v1.read_namespaced_pod(
            name=pod_name, namespace=os.environ["AKS_NAMESPACE"]
        )
        # load the cronjob manifest template and update PLACEHOLDER values with correct values using the pod spec
        with open("indexing-job-manager-template.yaml", "r") as f:
            manifest = yaml.safe_load(f)
        manifest["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0][
            "image"
        ] = pod.spec.containers[0].image
        manifest["spec"]["jobTemplate"]["spec"]["template"]["spec"][
            "serviceAccountName"
        ] = pod.spec.service_account_name
        # retrieve list of existing cronjobs
        batch_v1 = client.BatchV1Api()
        namespace_cronjobs = batch_v1.list_namespaced_cron_job(namespace="graphrag")
        cronjob_names = [cronjob.metadata.name for cronjob in namespace_cronjobs.items]
        # create cronjob if it does not exist
        if manifest["metadata"]["name"] not in cronjob_names:
            batch_v1.create_namespaced_cron_job(namespace="graphrag", body=manifest)
    except Exception as e:
        print(f"Failed to create graphrag cronjob.\n{e}")
        reporter = ReporterSingleton().get_instance()
        reporter.on_error(
            message="Failed to create graphrag cronjob",
            cause=str(e),
            stack=traceback.format_exc(),
        )
    yield  # This is where the application starts up.
    # shutdown/garbage collection code goes here


app = FastAPI(
    docs_url="/manpage/docs",
    openapi_url="/manpage/openapi.json",
    title="GraphRAG",
    version=os.getenv("GRAPHRAG_VERSION", "undefined_version"),
    lifespan=lifespan,
)
app.middleware("http")(catch_all_exceptions_middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
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
