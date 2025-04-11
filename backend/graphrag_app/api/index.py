# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import traceback
from time import time

from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    status,
)
from graphrag.config.enums import IndexingMethod
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
    delete_cosmos_container_item_if_exist,
    delete_storage_container_if_exist,
    get_cosmos_container_store_client,
    sanitize_name,
    subscription_key_check,
)
from graphrag_app.utils.pipeline import PipelineJob

index_route = APIRouter(
    prefix="/index",
    tags=["Index Operations"],
)
if os.getenv("KUBERNETES_SERVICE_HOST"):
    index_route.dependencies.append(Depends(subscription_key_check))


@index_route.post(
    "",
    summary="Build an index",
    response_model=BaseResponse,
    responses={status.HTTP_202_ACCEPTED: {"model": BaseResponse}},
)
async def schedule_index_job(
    storage_container_name: str,
    index_container_name: str,
    entity_extraction_prompt: UploadFile | None = None,
    entity_summarization_prompt: UploadFile | None = None,
    community_summarization_graph_prompt: UploadFile | None = None,
    community_summarization_text_prompt: UploadFile | None = None,
    indexing_method: IndexingMethod = IndexingMethod.Standard.value,
):
    indexing_method = IndexingMethod(indexing_method).value

    azure_client_manager = AzureClientManager()
    blob_service_client = azure_client_manager.get_blob_service_client()
    pipelinejob = PipelineJob()

    # validate index name against blob container naming rules
    sanitized_index_container_name = sanitize_name(index_container_name)

    # check for data container existence
    sanitized_storage_container_name = sanitize_name(storage_container_name)
    if not blob_service_client.get_container_client(
        sanitized_storage_container_name
    ).exists():
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=f"Storage container '{storage_container_name}' does not exist",
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
    community_summarization_graph_content = (
        community_summarization_graph_prompt.file.read().decode("utf-8")
        if community_summarization_graph_prompt
        else None
    )
    community_summarization_text_content = (
        community_summarization_text_prompt.file.read().decode("utf-8")
        if community_summarization_text_prompt
        else None
    )

    # check for existing index job
    # it is okay if job doesn't exist, but if it does,
    # it must not be scheduled or running
    if pipelinejob.item_exist(sanitized_index_container_name):
        existing_job = pipelinejob.load_item(sanitized_index_container_name)
        if (PipelineJobState(existing_job.status) == PipelineJobState.SCHEDULED) or (
            PipelineJobState(existing_job.status) == PipelineJobState.RUNNING
        ):
            raise HTTPException(
                status_code=status.HTTP_425_TOO_EARLY,  # request has been accepted for processing but is not complete.
                detail=f"Index '{index_container_name}' already exists and has not finished building.",
            )
        # if indexing job is in a failed state, delete the associated K8s job and pod to allow for a new job to be scheduled
        if PipelineJobState(existing_job.status) == PipelineJobState.FAILED:
            _delete_k8s_job(
                f"indexing-job-{sanitized_index_container_name}",
                os.environ["AKS_NAMESPACE"],
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
        existing_job.community_summarization_graph_prompt = (
            community_summarization_graph_content
        )
        existing_job.community_summarization_text_prompt = (
            community_summarization_text_content
        )
        existing_job._indexing_method = indexing_method

        existing_job._epoch_request_time = int(time())
        existing_job.update_db()
    else:
        pipelinejob.create_item(
            id=sanitized_index_container_name,
            human_readable_index_name=index_container_name,
            human_readable_storage_name=storage_container_name,
            entity_extraction_prompt=entity_extraction_prompt_content,
            entity_summarization_prompt=entity_summarization_prompt_content,
            community_summarization_graph_prompt=community_summarization_graph_content,
            community_summarization_text_prompt=community_summarization_text_content,
            indexing_method=indexing_method,
            status=PipelineJobState.SCHEDULED,
        )

    return BaseResponse(status="Indexing job scheduled")


@index_route.get(
    "",
    summary="Get all index names",
    response_model=IndexNameList,
    responses={status.HTTP_200_OK: {"model": IndexNameList}},
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
                items.append(item["human_readable_index_name"])
    except Exception as e:
        logger = load_pipeline_logger()
        logger.error(
            message="Error fetching index list",
            cause=e,
            stack=traceback.format_exc(),
        )
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
    except Exception as e:
        logger.error(
            message=f"Error deleting k8s job {job_name}.",
            cause=e,
            stack=traceback.format_exc(),
            details={"container": job_name},
        )
        pass
    try:
        core_v1 = kubernetes_client.CoreV1Api()
        job_pod = _get_pod_name(job_name, os.environ["AKS_NAMESPACE"])
        if job_pod:
            core_v1.delete_namespaced_pod(job_pod, namespace=namespace)
    except Exception as e:
        logger.error(
            message=f"Error deleting k8s pod for job {job_name}.",
            cause=e,
            stack=traceback.format_exc(),
            details={"container": job_name},
        )
        pass


@index_route.delete(
    "/{container_name}",
    summary="Delete a specified index",
    response_model=BaseResponse,
    responses={status.HTTP_200_OK: {"model": BaseResponse}},
)
async def delete_index(
    container_name: str,
    sanitized_container_name: str = Depends(sanitize_name),
):
    """
    Delete a specified index and all associated metadata.
    """
    try:
        # kill indexing job if it is running
        if os.getenv("KUBERNETES_SERVICE_HOST"):  # only found if in AKS
            _delete_k8s_job(f"indexing-job-{sanitized_container_name}", "graphrag")

        delete_storage_container_if_exist(sanitized_container_name)
        delete_cosmos_container_item_if_exist(
            "container-store", sanitized_container_name
        )
        delete_cosmos_container_item_if_exist("jobs", sanitized_container_name)

        # delete associated AI Search index
        index_client = SearchIndexClient(
            endpoint=os.environ["AI_SEARCH_URL"],
            credential=DefaultAzureCredential(),
            audience=os.environ["AI_SEARCH_AUDIENCE"],
        )
        
        index_names = index_client.list_index_names()
        ai_search_index_report_name = f"{sanitized_container_name}-community-full_content"
        if ai_search_index_report_name in index_names:
            index_client.delete_index(ai_search_index_report_name)
        
        ai_search_index_description_name = f"{sanitized_container_name}-entity-description"
        if ai_search_index_description_name in index_names:
            index_client.delete_index(ai_search_index_description_name)
        
        ai_search_index_text_name = f"{sanitized_container_name}-text_unit-text"
        if ai_search_index_text_name in index_names:
            index_client.delete_index(ai_search_index_text_name)

    except Exception as e:
        logger = load_pipeline_logger()
        logger.error(
            message=f"Error encountered while deleting all data for {container_name}.",
            cause=e,
            stack=traceback.format_exc(),
            details={"container": container_name},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting '{container_name}'.",
        )

    return BaseResponse(status="Success")


@index_route.get(
    "/status/{container_name}",
    summary="Track the status of an indexing job",
    response_model=IndexStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_index_status(
    container_name: str, sanitized_container_name: str = Depends(sanitize_name)
):
    pipelinejob = PipelineJob()
    if pipelinejob.item_exist(sanitized_container_name):
        pipeline_job = pipelinejob.load_item(sanitized_container_name)
        return IndexStatusResponse(
            status_code=status.HTTP_200_OK,
            index_name=pipeline_job.human_readable_index_name,
            storage_name=pipeline_job.human_readable_storage_name,
            status=pipeline_job.status.value,
            percent_complete=pipeline_job.percent_complete,
            progress=pipeline_job.progress,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"'{container_name}' does not exist.",
        )
