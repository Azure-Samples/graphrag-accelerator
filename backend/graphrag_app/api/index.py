# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
from time import time

from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
)
from kubernetes import (
    client as kubernetes_client,
)
from kubernetes import (
    config as kubernetes_config,
)

from graphrag_app.logger.load_logger import load_pipeline_logger
from graphrag_app.typing.models import (
    BaseResponse,
    IndexNameList,
    IndexStatusResponse,
)
from graphrag_app.typing.pipeline import PipelineJobState
from graphrag_app.utils.azure_clients import AzureClientManager
from graphrag_app.utils.common import (
    delete_blob_container,
    delete_cosmos_container_item,
    desanitize_name,
    get_cosmos_container_store_client,
    sanitize_name,
    validate_blob_container_name,
)
from graphrag_app.utils.pipeline import PipelineJob

index_route = APIRouter(
    prefix="/index",
    tags=["Index Operations"],
)


@index_route.post(
    "",
    summary="Build an index",
    response_model=BaseResponse,
    responses={200: {"model": BaseResponse}},
)
async def schedule_index_job(
    storage_name: str,
    index_name: str,
    entity_extraction_prompt: UploadFile | None = None,
    entity_summarization_prompt: UploadFile | None = None,
    community_summarization_prompt: UploadFile | None = None,
):
    azure_client_manager = AzureClientManager()
    blob_service_client = azure_client_manager.get_blob_service_client()
    pipelinejob = PipelineJob()

    # validate index name against blob container naming rules
    sanitized_index_name = sanitize_name(index_name)
    try:
        validate_blob_container_name(sanitized_index_name)
    except ValueError:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid index name: {index_name}",
        )

    # check for data container existence
    sanitized_storage_name = sanitize_name(storage_name)
    if not blob_service_client.get_container_client(sanitized_storage_name).exists():
        raise HTTPException(
            status_code=500,
            detail=f"Storage blob container {storage_name} does not exist",
        )

    # check for prompts
    entity_extraction_prompt_content = (
        entity_extraction_prompt.file.read().decode("utf-8")
        if entity_extraction_prompt
        else None
    )
    entity_summarization_prompt_content = (
        entity_summarization_prompt.file.read().decode("utf-8")
        if entity_summarization_prompt
        else None
    )
    community_summarization_prompt_content = (
        community_summarization_prompt.file.read().decode("utf-8")
        if community_summarization_prompt
        else None
    )

    # check for existing index job
    # it is okay if job doesn't exist, but if it does,
    # it must not be scheduled or running
    if pipelinejob.item_exist(sanitized_index_name):
        existing_job = pipelinejob.load_item(sanitized_index_name)
        if (PipelineJobState(existing_job.status) == PipelineJobState.SCHEDULED) or (
            PipelineJobState(existing_job.status) == PipelineJobState.RUNNING
        ):
            raise HTTPException(
                status_code=202,  # request has been accepted for processing but is not complete.
                detail=f"Index '{index_name}' already exists and has not finished building.",
            )
        # if indexing job is in a failed state, delete the associated K8s job and pod to allow for a new job to be scheduled
        if PipelineJobState(existing_job.status) == PipelineJobState.FAILED:
            _delete_k8s_job(
                f"indexing-job-{sanitized_index_name}", os.environ["AKS_NAMESPACE"]
            )
        # reset the pipeline job details
        existing_job._status = PipelineJobState.SCHEDULED
        existing_job._percent_complete = 0
        existing_job._progress = ""
        existing_job._all_workflows = existing_job._completed_workflows = (
            existing_job._failed_workflows
        ) = []
        existing_job._entity_extraction_prompt = entity_extraction_prompt_content
        existing_job._entity_summarization_prompt = entity_summarization_prompt_content
        existing_job._community_summarization_prompt = (
            community_summarization_prompt_content
        )
        existing_job._epoch_request_time = int(time())
        existing_job.update_db()
    else:
        pipelinejob.create_item(
            id=sanitized_index_name,
            human_readable_index_name=index_name,
            human_readable_storage_name=storage_name,
            entity_extraction_prompt=entity_extraction_prompt_content,
            entity_summarization_prompt=entity_summarization_prompt_content,
            community_summarization_prompt=community_summarization_prompt_content,
            status=PipelineJobState.SCHEDULED,
        )

    return BaseResponse(status="Indexing job scheduled")


@index_route.get(
    "",
    summary="Get all index names",
    response_model=IndexNameList,
    responses={200: {"model": IndexNameList}},
)
async def get_all_index_names(
    container_store_client=Depends(get_cosmos_container_store_client),
):
    """
    Retrieve a list of all index names.
    """
    items = []
    try:
        for item in container_store_client.read_all_items():
            if item["type"] == "index":
                items.append(item["human_readable_name"])
    except Exception:
        logger = load_pipeline_logger()
        logger.error("Error fetching index list")
    return IndexNameList(index_name=items)


def _get_pod_name(job_name: str, namespace: str) -> str | None:
    """Retrieve the name of a kubernetes pod associated with a given job name."""
    # function should work only when running in AKS
    if not os.getenv("KUBERNETES_SERVICE_HOST"):
        return None
    kubernetes_config.load_incluster_config()
    v1 = kubernetes_client.CoreV1Api()
    ret = v1.list_namespaced_pod(namespace=namespace)
    for i in ret.items:
        if job_name in i.metadata.name:
            return i.metadata.name
    return None


def _delete_k8s_job(job_name: str, namespace: str) -> None:
    """Delete a kubernetes job.
    Must delete K8s job first and then any pods associated with it
    """
    # function should only work when running in AKS
    if not os.getenv("KUBERNETES_SERVICE_HOST"):
        return None
    logger = load_pipeline_logger()
    kubernetes_config.load_incluster_config()
    try:
        batch_v1 = kubernetes_client.BatchV1Api()
        batch_v1.delete_namespaced_job(name=job_name, namespace=namespace)
    except Exception:
        logger.error(
            message=f"Error deleting k8s job {job_name}.",
            details={"container": job_name},
        )
        pass
    try:
        core_v1 = kubernetes_client.CoreV1Api()
        job_pod = _get_pod_name(job_name, os.environ["AKS_NAMESPACE"])
        if job_pod:
            core_v1.delete_namespaced_pod(job_pod, namespace=namespace)
    except Exception:
        logger.error(
            message=f"Error deleting k8s pod for job {job_name}.",
            details={"container": job_name},
        )
        pass


@index_route.delete(
    "/{index_name}",
    summary="Delete a specified index",
    response_model=BaseResponse,
    responses={200: {"model": BaseResponse}},
)
async def delete_index(
    sanitized_container_name: str = Depends(sanitize_name),
):
    """
    Delete a specified index.
    """
    try:
        # kill indexing job if it is running
        if os.getenv("KUBERNETES_SERVICE_HOST"):  # only found if in AKS
            _delete_k8s_job(f"indexing-job-{sanitized_container_name}", "graphrag")

        # delete blob container
        delete_blob_container(sanitized_container_name)

        # delete entry from "container-store" container in cosmosDB
        delete_cosmos_container_item("container-store", sanitized_container_name)

        # delete entry from "jobs" container in cosmosDB
        delete_cosmos_container_item("jobs", sanitized_container_name)

        index_client = SearchIndexClient(
            endpoint=os.environ["AI_SEARCH_URL"],
            credential=DefaultAzureCredential(),
            audience=os.environ["AI_SEARCH_AUDIENCE"],
        )
        ai_search_index_name = f"{sanitized_container_name}_description_embedding"
        if ai_search_index_name in index_client.list_index_names():
            index_client.delete_index(ai_search_index_name)

    except Exception:
        logger = load_pipeline_logger()
        original_container_name = desanitize_name(sanitized_container_name)
        logger.error(
            message=f"Error encountered while deleting all data for {original_container_name}.",
            stack=None,
            details={"container": original_container_name},
        )
        raise HTTPException(
            status_code=500, detail=f"Error deleting '{original_container_name}'."
        )

    return BaseResponse(status="Success")


@index_route.get(
    "/status/{index_name}",
    summary="Track the status of an indexing job",
    response_model=IndexStatusResponse,
)
async def get_index_job_status(sanitized_container_name: str = Depends(sanitize_name)):
    pipelinejob = PipelineJob()
    if pipelinejob.item_exist(sanitized_container_name):
        pipeline_job = pipelinejob.load_item(sanitized_container_name)
        return IndexStatusResponse(
            status_code=200,
            index_name=pipeline_job.human_readable_index_name,
            storage_name=pipeline_job.human_readable_storage_name,
            status=pipeline_job.status.value,
            percent_complete=pipeline_job.percent_complete,
            progress=pipeline_job.progress,
        )
    else:
        original_container_name = desanitize_name(sanitized_container_name)
        raise HTTPException(
            status_code=404, detail=f"'{original_container_name}' does not exist."
        )
