# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import asyncio
import inspect
import os
import traceback
from typing import cast

import yaml
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from datashaper import WorkflowCallbacksManager
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
)
from graphrag.config import create_graphrag_config
from graphrag.index import create_pipeline_config
from graphrag.index.bootstrap import bootstrap
from graphrag.index.run import run_pipeline_with_config
from kubernetes import (
    client,
    config,
)
from kubernetes.client.rest import ApiException

from src.api.azure_clients import (
    AzureStorageClientManager,
    BlobServiceClientSingleton,
    get_database_container_client,
)
from src.api.common import (
    delete_blob_container,
    retrieve_original_blob_container_name,
    sanitize_name,
    validate_blob_container_name,
    verify_subscription_key_exist,
)
from src.models import (
    BaseResponse,
    IndexNameList,
    IndexStatusResponse,
    PipelineJob,
)
from src.reporting import ReporterSingleton
from src.reporting.load_reporter import load_pipeline_reporter
from src.reporting.pipeline_job_workflow_callbacks import PipelineJobWorkflowCallbacks
from src.reporting.typing import Reporters
from src.typing import PipelineJobState

blob_service_client = BlobServiceClientSingleton.get_instance()
azure_storage_client_manager = (
    AzureStorageClientManager()
)  # TODO: update API to use the AzureStorageClientManager

ai_search_url = os.environ["AI_SEARCH_URL"]
ai_search_audience = os.environ["AI_SEARCH_AUDIENCE"]

index_route = APIRouter(
    prefix="/index",
    tags=["Index Operations"],
)

if os.getenv("KUBERNETES_SERVICE_HOST"):
    index_route.dependencies.append(Depends(verify_subscription_key_exist))


@index_route.post(
    "",
    summary="Build an index",
    response_model=BaseResponse,
    responses={200: {"model": BaseResponse}},
)
async def setup_indexing_pipeline(
    storage_name: str,
    index_name: str,
    entity_extraction_prompt: UploadFile | None = None,
    community_report_prompt: UploadFile | None = None,
    summarize_descriptions_prompt: UploadFile | None = None,
):
    _blob_service_client = BlobServiceClientSingleton().get_instance()
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
    if not _blob_service_client.get_container_client(sanitized_storage_name).exists():
        raise HTTPException(
            status_code=500,
            detail=f"Data container '{storage_name}' does not exist.",
        )

    # check for prompts
    entity_extraction_prompt_content = (
        entity_extraction_prompt.file.read().decode("utf-8")
        if entity_extraction_prompt
        else None
    )
    community_report_prompt_content = (
        community_report_prompt.file.read().decode("utf-8")
        if community_report_prompt
        else None
    )
    summarize_descriptions_prompt_content = (
        summarize_descriptions_prompt.file.read().decode("utf-8")
        if summarize_descriptions_prompt
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
                detail=f"an index with name {index_name} already exists and has not finished building.",
            )
        # if indexing job is in a failed state, delete the associated K8s job and pod to allow for a new job to be scheduled
        if PipelineJobState(existing_job.status) == PipelineJobState.FAILED:
            _delete_k8s_job(f"indexing-job-{sanitized_index_name}", "graphrag")
        # reset the pipeline job details
        existing_job._status = PipelineJobState.SCHEDULED
        existing_job._percent_complete = 0
        existing_job._progress = ""
        existing_job._all_workflows = existing_job._completed_workflows = (
            existing_job._failed_workflows
        ) = []
        existing_job._entity_extraction_prompt = entity_extraction_prompt_content
        existing_job._community_report_prompt = community_report_prompt_content
        existing_job._summarize_descriptions_prompt = (
            summarize_descriptions_prompt_content
        )
        existing_job.update_db()
    else:
        pipelinejob.create_item(
            id=sanitized_index_name,
            index_name=sanitized_index_name,
            storage_name=sanitized_storage_name,
            entity_extraction_prompt=entity_extraction_prompt_content,
            community_report_prompt=community_report_prompt_content,
            summarize_descriptions_prompt=summarize_descriptions_prompt_content,
            status=PipelineJobState.SCHEDULED,
        )

    """
    At this point, we know:
    1) the index name is valid
    2) the data container exists
    3) there is no indexing job with this name currently running or a previous job has finished
    """
    # update or create new item in container-store in cosmosDB
    if not _blob_service_client.get_container_client(sanitized_index_name).exists():
        _blob_service_client.create_container(sanitized_index_name)
    container_store_client = get_database_container_client(
        database_name="graphrag", container_name="container-store"
    )
    container_store_client.upsert_item(
        {
            "id": sanitized_index_name,
            "human_readable_name": index_name,
            "type": "index",
        }
    )

    # schedule AKS job
    try:
        config.load_incluster_config()
        # get container image name
        core_v1 = client.CoreV1Api()
        pod_name = os.environ["HOSTNAME"]
        pod = core_v1.read_namespaced_pod(
            name=pod_name, namespace=os.environ["AKS_NAMESPACE"]
        )
        # retrieve job manifest template and replace necessary values
        job_manifest = _generate_aks_job_manifest(
            docker_image_name=pod.spec.containers[0].image,
            index_name=index_name,
            service_account_name=pod.spec.service_account_name,
        )
        try:
            batch_v1 = client.BatchV1Api()
            batch_v1.create_namespaced_job(
                body=job_manifest, namespace=os.environ["AKS_NAMESPACE"]
            )
        except ApiException:
            raise HTTPException(
                status_code=500,
                detail="exception when calling BatchV1Api->create_namespaced_job",
            )
        return BaseResponse(status="indexing operation has been scheduled.")
    except Exception:
        reporter = ReporterSingleton().get_instance()
        job_details = {
            "storage_name": storage_name,
            "index_name": index_name,
        }
        reporter.on_error(
            "Error creating a new index",
            details={"job_details": job_details},
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error occurred during setup of indexing job for '{index_name}'.",
        )


async def _start_indexing_pipeline(index_name: str):
    # get sanitized name
    sanitized_index_name = sanitize_name(index_name)

    reporter = ReporterSingleton().get_instance()
    pipelinejob = PipelineJob()
    pipeline_job = pipelinejob.load_item(sanitized_index_name)
    sanitized_storage_name = pipeline_job.storage_name
    storage_name = retrieve_original_blob_container_name(sanitized_storage_name)

    # download nltk dependencies
    bootstrap()

    # create new reporters/callbacks just for this job
    reporters = []
    reporter_names = os.getenv("REPORTERS", Reporters.CONSOLE.name.upper()).split(",")
    for reporter_name in reporter_names:
        try:
            reporters.append(Reporters[reporter_name.upper()])
        except KeyError:
            raise ValueError(f"Found unknown reporter: {reporter_name}")

    workflow_callbacks = load_pipeline_reporter(
        reporting_dir=sanitized_index_name, reporters=reporters
    )

    # load custom pipeline settings
    this_directory = os.path.dirname(
        os.path.abspath(inspect.getfile(inspect.currentframe()))
    )
    data = yaml.safe_load(open(f"{this_directory}/pipeline-settings.yaml"))
    # dynamically set some values
    data["input"]["container_name"] = sanitized_storage_name
    data["storage"]["container_name"] = sanitized_index_name
    data["reporting"]["container_name"] = sanitized_index_name
    data["cache"]["container_name"] = sanitized_index_name
    if "vector_store" in data["embeddings"]:
        data["embeddings"]["vector_store"]["collection_name"] = (
            f"{sanitized_index_name}_description_embedding"
        )

    # set prompts for entity extraction, community report, and summarize descriptions.
    if pipeline_job.entity_extraction_prompt:
        fname = "entity-extraction-prompt.txt"
        with open(fname, "w") as outfile:
            outfile.write(pipeline_job.entity_extraction_prompt)
        data["entity_extraction"]["prompt"] = fname
    else:
        data.pop("entity_extraction")
    if pipeline_job.community_report_prompt:
        fname = "community-report-prompt.txt"
        with open(fname, "w") as outfile:
            outfile.write(pipeline_job.community_report_prompt)
        data["community_reports"]["prompt"] = fname
    else:
        data.pop("community_reports")
    if pipeline_job.summarize_descriptions_prompt:
        fname = "summarize-descriptions-prompt.txt"
        with open(fname, "w") as outfile:
            outfile.write(pipeline_job.summarize_descriptions_prompt)
        data["summarize_descriptions"]["prompt"] = fname
    else:
        data.pop("summarize_descriptions")

    # generate the default pipeline and override with custom settings
    parameters = create_graphrag_config(data, ".")
    pipeline_config = create_pipeline_config(parameters, True)

    # reset pipeline job details
    pipeline_job.status = PipelineJobState.RUNNING
    pipeline_job.all_workflows = []
    pipeline_job.completed_workflows = []
    pipeline_job.failed_workflows = []
    for workflow in pipeline_config.workflows:
        pipeline_job.all_workflows.append(workflow.name)

    # add pipeline_job callback to the callback manager
    cast(WorkflowCallbacksManager, workflow_callbacks).register(
        PipelineJobWorkflowCallbacks(pipeline_job)
    )

    # run the pipeline
    try:
        async for workflow_result in run_pipeline_with_config(
            config_or_path=pipeline_config,
            callbacks=workflow_callbacks,
            progress_reporter=None,
        ):
            await asyncio.sleep(0)
            if len(workflow_result.errors or []) > 0:
                # if the workflow failed, record the failure
                pipeline_job.failed_workflows.append(workflow_result.workflow)
                pipeline_job.update_db()

        # if job is done, check if any workflow steps failed
        if len(pipeline_job.failed_workflows) > 0:
            pipeline_job.status = PipelineJobState.FAILED
        else:
            # record the workflow completion
            pipeline_job.status = PipelineJobState.COMPLETE
            pipeline_job.percent_complete = 100

        pipeline_job.progress = (
            f"{len(pipeline_job.completed_workflows)} out of "
            f"{len(pipeline_job.all_workflows)} workflows completed successfully."
        )

        workflow_callbacks.on_log(
            f"Index Name: {index_name}, Container Name: {storage_name}\n",
            details={"status_message": "Indexing pipeline complete."},
        )

        del workflow_callbacks  # garbage collect
        if pipeline_job.status == PipelineJobState.FAILED:
            exit(1)  # signal to AKS that indexing job failed

    except Exception:
        pipeline_job.status = PipelineJobState.FAILED

        # update failed state in cosmos db
        error_details = {
            "error_message": "Indexing pipeline failed.",
        }
        # log error in local index directory logs
        workflow_callbacks.on_error(
            message=f"Index Name: {index_name}, Container Name: {storage_name}\n",
            cause=None,
            stack=None,
            details=error_details,
        )
        # log error in global index directory logs
        reporter.on_error(
            f"Index Name: {index_name}, Container Name: {storage_name}\n {str(e)} \n",
            cause=str(e),
            stack=None,
            details=error_details,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error occurred during indexing job for index '{index_name}'.",
        )


def _generate_aks_job_manifest(
    docker_image_name: str,
    index_name: str,
    service_account_name: str,
) -> dict:
    """Generate an AKS Jobs manifest file with the specified parameters.

    The manifest file must be valid YAML with certain values replaced by the provided arguments.
    """
    # NOTE: the relative file locations are based on the WORKDIR set in Dockerfile-indexing
    with open("src/aks-batch-job-template.yaml", "r") as f:
        manifest = yaml.safe_load(f)
    manifest["metadata"]["name"] = f"indexing-job-{sanitize_name(index_name)}"
    manifest["spec"]["template"]["spec"]["serviceAccountName"] = service_account_name
    manifest["spec"]["template"]["spec"]["containers"][0]["image"] = docker_image_name
    manifest["spec"]["template"]["spec"]["containers"][0]["command"] = [
        "python",
        "run-indexing-job.py",
        f"-i={index_name}",
    ]
    return manifest


@index_route.get(
    "",
    summary="Get all indexes",
    response_model=IndexNameList,
    responses={200: {"model": IndexNameList}},
)
async def get_all_indexes():
    """
    Retrieve a list of all index names.
    """
    items = []
    try:
        container_store_client = get_database_container_client(
            database_name="graphrag", container_name="container-store"
        )
        for item in container_store_client.read_all_items():
            if item["type"] == "index":
                items.append(item["human_readable_name"])
    except Exception:
        reporter = ReporterSingleton().get_instance()
        reporter.on_error("Error retrieving index names")
    return IndexNameList(index_name=items)


def _get_pod_name(job_name: str, namespace: str) -> str | None:
    """Retrieve the name of a kubernetes pod associated with a given job name."""
    # function should work only when running in AKS
    if not os.getenv("KUBERNETES_SERVICE_HOST"):
        return None
    config.load_incluster_config()
    v1 = client.CoreV1Api()
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
    reporter = ReporterSingleton().get_instance()
    config.load_incluster_config()
    try:
        batch_v1 = client.BatchV1Api()
        batch_v1.delete_namespaced_job(name=job_name, namespace=namespace)
    except Exception:
        reporter.on_error(
            f"Error deleting k8s job {job_name}.",
            details={"Container": job_name},
        )
        pass
    try:
        core_v1 = client.CoreV1Api()
        job_pod = _get_pod_name(job_name, os.environ["AKS_NAMESPACE"])
        if job_pod:
            core_v1.delete_namespaced_pod(job_pod, namespace=namespace)
    except Exception:
        reporter.on_error(
            f"Error deleting k8s pod for job {job_name}.",
            details={"Container": job_name},
        )
        pass


@index_route.delete(
    "/{index_name}",
    summary="Delete a specified index",
    response_model=BaseResponse,
    responses={200: {"model": BaseResponse}},
)
async def delete_index(index_name: str):
    """
    Delete a specified index.
    """
    sanitized_index_name = sanitize_name(index_name)
    reporter = ReporterSingleton().get_instance()
    try:
        # kill indexing job if it is running
        if os.getenv("KUBERNETES_SERVICE_HOST"):  # only found if in AKS
            _delete_k8s_job(f"indexing-job-{sanitized_index_name}", "graphrag")

        # remove blob container and all associated entries in cosmos db
        try:
            delete_blob_container(sanitized_index_name)
        except Exception:
            pass

        # update container-store in cosmosDB
        try:
            container_store_client = get_database_container_client(
                database_name="graphrag", container_name="container-store"
            )
            container_store_client.delete_item(
                item=sanitized_index_name, partition_key=sanitized_index_name
            )
        except Exception:
            pass

        # update jobs database in cosmosDB
        try:
            jobs_container = get_database_container_client(
                database_name="graphrag", container_name="jobs"
            )
            jobs_container.delete_item(
                item=sanitized_index_name, partition_key=sanitized_index_name
            )
        except Exception:
            pass

        index_client = SearchIndexClient(
            endpoint=ai_search_url,
            credential=DefaultAzureCredential(),
            audience=ai_search_audience,
        )
        ai_search_index_name = f"{sanitized_index_name}_description_embedding"
        if ai_search_index_name in index_client.list_index_names():
            index_client.delete_index(ai_search_index_name)

    except Exception:
        reporter.on_error(
            message=f"Error encountered while deleting all data for index {index_name}.",
            stack=None,
            details={"container": index_name},
        )
        raise HTTPException(
            status_code=500, detail=f"Error deleting index '{index_name}'."
        )

    return BaseResponse(status="Success")


@index_route.get(
    "/status/{index_name}",
    summary="Track the status of an indexing job",
    response_model=IndexStatusResponse,
)
async def get_index_job_status(index_name: str):
    pipelinejob = PipelineJob()  # TODO: fix class so initiliazation is not required
    sanitized_index_name = sanitize_name(index_name)
    if pipelinejob.item_exist(sanitized_index_name):
        pipeline_job = pipelinejob.load_item(sanitized_index_name)
        return IndexStatusResponse(
            status_code=200,
            index_name=retrieve_original_blob_container_name(pipeline_job.index_name),
            storage_name=retrieve_original_blob_container_name(
                pipeline_job.storage_name
            ),
            status=pipeline_job.status.value,
            percent_complete=pipeline_job.percent_complete,
            progress=pipeline_job.progress,
        )
    raise HTTPException(status_code=404, detail=f"Index '{index_name}' does not exist.")
