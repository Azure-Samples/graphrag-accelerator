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
    BackgroundTasks,
    Depends,
    HTTPException,
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
    retrieve_original_entity_config_name,
    sanitize_name,
    validate_blob_container_name,
    verify_subscription_key_exist,
)
from src.api.index_configuration import get_entity
from src.models import (
    BaseResponse,
    IndexNameList,
    IndexRequest,
    IndexStatusResponse,
    PipelineJob,
)
from src.prompts import graph_extraction_prompt
from src.reporting import ReporterSingleton
from src.reporting.load_reporter import load_pipeline_reporter
from src.reporting.pipeline_job_workflow_callbacks import PipelineJobWorkflowCallbacks
from src.reporting.reporter_singleton import send_webhook
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
def setup_indexing_pipeline(
    request: IndexRequest, background_tasks: BackgroundTasks = None
):
    _blob_service_client = BlobServiceClientSingleton().get_instance()
    pipelinejob = PipelineJob()  # TODO: fix class so initiliazation is not required

    # validate index name against blob container naming rules
    sanitized_index_name = sanitize_name(request.index_name)
    try:
        validate_blob_container_name(sanitized_index_name)
    except ValueError:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid index name: {request.index_name}",
        )

    # check for data container existence
    sanitized_storage_name = sanitize_name(request.storage_name)
    if not _blob_service_client.get_container_client(sanitized_storage_name).exists():
        raise HTTPException(
            status_code=500,
            detail=f"Data container '{request.storage_name}' does not exist.",
        )

    # check for entity configuration existence
    sanitized_entity_config_name = sanitize_name(request.entity_config_name)
    if request.entity_config_name:
        entity_container_client = get_database_container_client(
            database_name="graphrag", container_name="entities"
        )
        try:
            entity_container_client.read_item(  # noqa
                item=sanitized_entity_config_name,
                partition_key=sanitized_entity_config_name,
            )
        except Exception:
            raise HTTPException(
                status_code=500,
                detail=f"Entity configuration '{request.entity_config_name}' does not exist.",
            )

    # check for existing index job
    # it is okay if job doesn't exist, but if it does,
    # it must not be scheduled or running
    if pipelinejob.item_exist(request.index_name):
        existing_job = pipelinejob.load_item(request.index_name)
        if (PipelineJobState(existing_job.status) == PipelineJobState.SCHEDULED) or (
            PipelineJobState(existing_job.status) == PipelineJobState.RUNNING
        ):
            raise HTTPException(
                status_code=202,  # request has been accepted for processing but is not complete.
                detail=f"an index with name {request.index_name} already exists and has not finished building.",
            )
        # if indexing job is in a failed state, delete the associated K8s job and pod to allow for a new job to be scheduled
        if PipelineJobState(existing_job.status) == PipelineJobState.FAILED:
            _delete_k8s_job(f"indexing-job-{request.index_name}", "graphrag")

        # reset the job to scheduled state
        existing_job.status = PipelineJobState.SCHEDULED
        existing_job.percent_complete = 0
        existing_job.progress = ""
    else:
        # create or update state in cosmos db
        pipelinejob.create_item(
            id=sanitized_index_name,
            index_name=sanitized_index_name,
            storage_name=sanitized_storage_name,
            entity_config_name=sanitized_entity_config_name,
            status=PipelineJobState.SCHEDULED,
        )

    """
    At this point, we know:
    1) the index name is valid
    2) the data container exists
    3) the entity configuration exists.
    4) there is no indexing job with this name currently running or a previous job has finished
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
            "human_readable_name": request.index_name,
            "type": "index",
        }
    )

    try:
        # schedule AKS job if possible
        if os.getenv("KUBERNETES_SERVICE_HOST"):  # only found if in AKS
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
                index_name=request.index_name,
                storage_name=request.storage_name,
                service_account_name=pod.spec.service_account_name,
                entity_config_name=request.entity_config_name,
            )
            print(f"Created job manifest:\n{job_manifest}")
            try:
                batch_v1 = client.BatchV1Api()
                batch_v1.create_namespaced_job(
                    body=job_manifest, namespace=os.environ["AKS_NAMESPACE"]
                )
            except ApiException as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"exception when calling BatchV1Api->create_namespaced_job: {str(e)}",
                )
        else:  # run locally
            if background_tasks:
                background_tasks.add_task(
                    _start_indexing_pipeline,
                    request.index_name,
                    request.storage_name,
                    request.entity_config_name,
                    request.webhook_url,
                )
        return BaseResponse(status="indexing operation has been scheduled.")
    except Exception as e:
        reporter = ReporterSingleton().get_instance()
        job_details = {
            "storage_name": request.storage_name,
            "index_name": request.index_name,
        }
        reporter.on_error(
            "Error creating a new index",
            details={"error_details": str(e), "job_details": job_details},
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error occurred during setup of indexing job for '{request.index_name}'.",
        )


async def _start_indexing_pipeline(
    index_name: str,
    storage_name: str,
    entity_config_name: str | None = None,
    webhook_url: str | None = None,
):
    # get sanitized names
    sanitized_index_name = sanitize_name(index_name)
    sanitized_storage_name = sanitize_name(storage_name)

    reporter = ReporterSingleton().get_instance()
    pipelinejob = PipelineJob()  # TODO: fix class so initiliazation is not required

    # download nltk dependencies
    bootstrap()  # todo: expose the quiet flag to the user

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
    data = yaml.safe_load(open(f"{this_directory}/pipeline_settings.yaml"))
    # dynamically set some values
    data["input"]["container_name"] = sanitized_storage_name
    data["storage"]["container_name"] = sanitized_index_name
    data["reporting"]["container_name"] = sanitized_index_name
    data["cache"]["container_name"] = sanitized_index_name
    if "vector_store" in data["embeddings"]:
        data["embeddings"]["vector_store"]["collection_name"] = (
            f"{sanitized_index_name}_description_embedding"
        )

    # if entity_config_name was provided, load entity configuration and incorporate into pipeline
    # otherwise, set prompt and entity types to None to use the default values provided by graphrag
    if entity_config_name:
        entity_configuration = get_entity(entity_config_name)
        data["entity_extraction"]["entity_types"] = entity_configuration.entity_types
        with open("entity-extraction-prompt.txt", "w") as f:
            prompt = graph_extraction_prompt.get_prompt(
                entity_types=entity_configuration.entity_types,
                entity_examples=entity_configuration.entity_examples,
            )
            f.write(prompt)
        data["entity_extraction"]["prompt"] = "entity-extraction-prompt.txt"
    else:
        data["entity_extraction"]["prompt"] = None
        data["entity_extraction"]["entity_types"] = None

    # generate the default pipeline from default parameters and override with custom settings
    parameters = create_graphrag_config(data, ".")
    pipeline_config = create_pipeline_config(parameters, True)

    # create a new pipeline job object
    pipeline_job = pipelinejob.load_item(sanitized_index_name)
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

    try:
        # run the pipeline
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

        # jobs are done, check if any failed
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

        # send webhook to teams chat
        send_webhook(
            url=webhook_url,
            summary=f"Index '{index_name}' completed successfully",
            title=f"Congratulations, your indexing job, '{index_name}', completed successfully",
            subtitle=f"Container: {storage_name}",
            index_name=index_name,
            note="No errors were found",
            job_status="Complete",
            reporter=workflow_callbacks,
        )
        del workflow_callbacks  # garbage collect
        if pipeline_job.status == PipelineJobState.FAILED:
            exit(1)  # signal to AKS that indexing job failed

    except Exception as e:
        pipeline_job.status = PipelineJobState.FAILED

        # update failed state in cosmos db
        error_details = {
            "error_details": str(e),
            "error_message": "Indexing pipeline failed.",
        }
        # log error in local index directory logs
        workflow_callbacks.on_error(
            message=f"Index Name: {index_name}, Container Name: {storage_name}\n",
            cause=e,
            stack=traceback.format_exc(),
            details=error_details,
        )
        # log error in global index directory logs
        reporter.on_error(
            f"Index Name: {index_name}, Container Name: {storage_name}\n {str(e)} \n",
            cause=str(e),
            stack=traceback.format_exc(),
            details=error_details,
        )
        # send webhook to teams chat
        send_webhook(
            url=webhook_url,
            summary=f"Index '{index_name}' failed to complete.",
            title=f"Unfortunately your index, '{index_name}', has failed.",
            subtitle=f"Container: {storage_name}",
            index_name=index_name,
            note=f"Error Details: {error_details['error_details']}",
            job_status="Failed",
            reporter=workflow_callbacks,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error occurred during indexing job for index '{index_name}'.",
        )


def _generate_aks_job_manifest(
    docker_image_name: str,
    storage_name: str,
    index_name: str,
    service_account_name: str,
    entity_config_name: str | None = None,
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
        f"-s={storage_name}",
    ]
    if entity_config_name:
        manifest["spec"]["template"]["spec"]["containers"][0]["command"].append(
            f"-e={entity_config_name}"
        )
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
    except Exception as e:
        reporter = ReporterSingleton().get_instance()
        reporter.on_error(f"Error retrieving index names: {str(e)}")
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
    except Exception as e:
        reporter.on_error(
            f"Error deleting k8s job {job_name}.",
            details={"error_details": str(e), "Container": job_name},
        )
        pass
    try:
        core_v1 = client.CoreV1Api()
        job_pod = _get_pod_name(job_name, os.environ["AKS_NAMESPACE"])
        if job_pod:
            core_v1.delete_namespaced_pod(job_pod, namespace=namespace)
    except Exception as e:
        reporter.on_error(
            f"Error deleting k8s pod for job {job_name}.",
            details={"error_details": str(e), "Container": job_name},
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
            audience=ai_search_audience
        )
        ai_search_index_name = f"{sanitized_index_name}_description_embedding"
        if ai_search_index_name in index_client.list_index_names():
            index_client.delete_index(ai_search_index_name)

    except Exception as e:
        reporter.on_error(
            message=f"Error encountered while deleting all data for index {index_name}.",
            stack=traceback.format_exc(),
            details={"error_details": str(e), "container": index_name},
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
            entity_config_name=retrieve_original_entity_config_name(
                pipeline_job.entity_config_name
            ),
            status=pipeline_job.status.value,
            percent_complete=pipeline_job.percent_complete,
            progress=pipeline_job.progress,
        )
    raise HTTPException(status_code=404, detail=f"Index '{index_name}' does not exist.")
