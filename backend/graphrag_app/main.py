# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from azure.cosmos import PartitionKey, ThroughputProperties
from fastapi import (
    FastAPI,
    Request,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi_offline import FastAPIOffline
from kubernetes import (
    client,
    config,
)

from graphrag_app.api.data import data_route
from graphrag_app.api.graph import graph_route
from graphrag_app.api.index import index_route
from graphrag_app.api.prompt_tuning import prompt_tuning_route
from graphrag_app.api.query import query_route
from graphrag_app.api.source import source_route
from graphrag_app.logger.load_logger import load_pipeline_logger
from graphrag_app.utils.azure_clients import AzureClientManager


async def catch_all_exceptions_middleware(request: Request, call_next):
    """a function to globally catch all exceptions and return a 500 response with the exception message"""
    try:
        return await call_next(request)
    except Exception as e:
        reporter = load_pipeline_logger()
        stack = traceback.format_exc()
        reporter.error(
            message="Unexpected internal server error",
            cause=e,
            stack=stack,
        )
        return Response("Unexpected internal server error.", status_code=500)


def intialize_cosmosdb_setup():
    """Initialise CosmosDB (if necessary) by setting up a database and containers that are expected at startup time."""
    azure_client_manager = AzureClientManager()
    client = azure_client_manager.get_cosmos_client()
    db_client = client.create_database_if_not_exists("graphrag")
    # create containers with default settings
    throughput = ThroughputProperties(
        auto_scale_max_throughput=1000, auto_scale_increment_percent=1
    )
    db_client.create_container_if_not_exists(
        id="jobs", partition_key=PartitionKey(path="/id"), offer_throughput=throughput
    )
    db_client.create_container_if_not_exists(
        id="container-store",
        partition_key=PartitionKey(path="/id"),
        offer_throughput=throughput,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Deploy a cronjob to manage indexing jobs.

    This function is called when the FastAPI application first starts up.
    To manage multiple graphrag indexing jobs, we deploy a k8s cronjob.
    This cronjob will act as a job manager that creates/manages the execution of graphrag indexing jobs as they are requested.
    """
    # if running in a TESTING environment, exit early to avoid creating k8s resources
    if os.getenv("TESTING"):
        yield
        return

    # Initialize CosmosDB setup
    intialize_cosmosdb_setup()

    try:
        # Check if the cronjob exists and create it if it does not exist
        config.load_incluster_config()
        # retrieve the running pod spec
        core_v1 = client.CoreV1Api()
        pod_name = os.environ["HOSTNAME"]
        pod = core_v1.read_namespaced_pod(
            name=pod_name, namespace=os.environ["AKS_NAMESPACE"]
        )
        # load the k8s cronjob template and update PLACEHOLDER values with correct values based on the running pod spec
        ROOT_DIR = Path(__file__).resolve().parent.parent
        with (ROOT_DIR / "manifests/cronjob.yaml").open("r") as f:
            manifest = yaml.safe_load(f)
        manifest["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0][
            "image"
        ] = pod.spec.containers[0].image
        manifest["spec"]["jobTemplate"]["spec"]["template"]["spec"][
            "serviceAccountName"
        ] = pod.spec.service_account_name
        # retrieve list of existing cronjobs
        batch_v1 = client.BatchV1Api()
        namespace_cronjobs = batch_v1.list_namespaced_cron_job(
            namespace=os.environ["AKS_NAMESPACE"]
        )
        cronjob_names = [cronjob.metadata.name for cronjob in namespace_cronjobs.items]
        # create cronjob if it does not exist
        if manifest["metadata"]["name"] not in cronjob_names:
            batch_v1.create_namespaced_cron_job(
                namespace=os.environ["AKS_NAMESPACE"], body=manifest
            )
    except Exception as e:
        print("Failed to create graphrag cronjob.")
        logger = load_pipeline_logger()
        logger.error(
            message="Failed to create graphrag cronjob",
            cause=str(e),
            stack=traceback.format_exc(),
        )
    yield  # This is where the application starts up.
    # shutdown/garbage collection code goes here


app = FastAPIOffline(
    docs_url="/manpage/docs",
    openapi_url="/manpage/openapi.json",
    root_path=os.getenv("API_ROOT_PATH", ""),
    title="GraphRAG",
    version=os.getenv("GRAPHRAG_VERSION", "undefined_version"),
    lifespan=lifespan
    if os.getenv("KUBERNETES_SERVICE_HOST")
    else None,  # only set lifespan if running in AKS (by checking for a default k8s environment variable)
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
# app.include_router(query_streaming_route) # temporarily disable streaming endpoints
app.include_router(prompt_tuning_route)
app.include_router(source_route)
app.include_router(graph_route)


# health check endpoint
@app.get(
    "/health",
    summary="API health check",
)
def health_check():
    """Returns a 200 response to indicate the API is healthy."""
    return Response(status_code=status.HTTP_200_OK)
