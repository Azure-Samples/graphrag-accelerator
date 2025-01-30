# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Note: This script is intended to be executed as a cron job on kubernetes.

A naive implementation of a job manager that leverages k8s CronJob and CosmosDB
to schedule graphrag indexing jobs on a first-come-first-serve basis (based on epoch time).
"""

import os
import traceback
from pathlib import Path

import pandas as pd
import yaml
from kubernetes import (
    client,
    config,
)

from graphrag_app.logger.load_logger import load_pipeline_logger
from graphrag_app.typing.pipeline import PipelineJobState
from graphrag_app.utils.azure_clients import AzureClientManager
from graphrag_app.utils.common import sanitize_name
from graphrag_app.utils.pipeline import PipelineJob


def schedule_indexing_job(index_name: str):
    """
    Schedule a k8s job to run graphrag indexing for a given index name.
    """
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
        batch_v1 = client.BatchV1Api()
        batch_v1.create_namespaced_job(
            body=job_manifest, namespace=os.environ["AKS_NAMESPACE"]
        )
    except Exception as e:
        reporter = load_pipeline_logger()
        reporter.error(
            message="Index job manager encountered error scheduling indexing job",
            cause=e,
            stack=traceback.format_exc(),
        )
        # In the event of a catastrophic scheduling failure, something in k8s or the job manifest is likely broken.
        # Set job status to failed to prevent an infinite loop of re-scheduling
        pipelinejob = PipelineJob()
        pipeline_job = pipelinejob.load_item(sanitize_name(index_name))
        pipeline_job["status"] = PipelineJobState.FAILED


def _generate_aks_job_manifest(
    docker_image_name: str,
    index_name: str,
    service_account_name: str,
) -> dict:
    """Generate an AKS Jobs manifest file with the specified parameters.

    The manifest must be valid YAML with certain values replaced by the provided arguments.
    """
    ROOT_DIR = Path(__file__).resolve().parent.parent
    with (ROOT_DIR / "manifests/job.yaml").open("r") as f:
        manifest = yaml.safe_load(f)
    manifest["metadata"]["name"] = f"indexing-job-{sanitize_name(index_name)}"
    manifest["spec"]["template"]["spec"]["serviceAccountName"] = service_account_name
    manifest["spec"]["template"]["spec"]["containers"][0]["image"] = docker_image_name
    manifest["spec"]["template"]["spec"]["containers"][0]["command"] = [
        "python",
        "indexer.py",
        f"-i={index_name}",
    ]
    return manifest


def list_k8s_jobs(namespace: str) -> list[str]:
    """List all k8s jobs in a given namespace."""
    config.load_incluster_config()
    batch_v1 = client.BatchV1Api()
    jobs = batch_v1.list_namespaced_job(namespace=namespace)
    job_list = []
    for job in jobs.items:
        if job.metadata.name.startswith("indexing-job-") and job.status.active:
            job_list.append(job.metadata.name)
    return job_list


def main():
    """
    There are two places to check to determine if an indexing job should be executed:
        * Kubernetes: check if there are any active k8s jobs running in the cluster
        * CosmosDB: check if there are any indexing jobs in a scheduled state

    Ideally if an indexing job has finished or failed, the job status will be reflected in cosmosdb.
    However, if an indexing job failed due to OOM, the job status will not have been updated in cosmosdb.

    To avoid a catastrophic failure scenario where all indexing jobs are stuck in a scheduled state,
    both checks are necessary.
    """
    kubernetes_jobs = list_k8s_jobs(os.environ["AKS_NAMESPACE"])

    azure_storage_client_manager = AzureClientManager()
    job_container_store_client = (
        azure_storage_client_manager.get_cosmos_container_client(
            database="graphrag", container="jobs"
        )
    )
    # retrieve status of all index jobs that are scheduled or running
    job_metadata = []
    for item in job_container_store_client.read_all_items():
        if item["status"] == PipelineJobState.RUNNING.value:
            # if index job has running state but no associated k8s job, a catastrophic
            # failure (OOM for example) occurred. Set job status to failed.
            if len(kubernetes_jobs) == 0:
                print(
                    f"Indexing job for '{item['human_readable_index_name']}' in 'running' state but no associated k8s job found. Updating to failed state."
                )
                pipelinejob = PipelineJob()
                pipeline_job = pipelinejob.load_item(item["sanitized_index_name"])
                pipeline_job.status = PipelineJobState.FAILED
            else:
                print(
                    f"Indexing job for '{item['human_readable_index_name']}' already running. Will not schedule another. Exiting..."
                )
                exit()
        if item["status"] == PipelineJobState.SCHEDULED.value:
            job_metadata.append({
                "human_readable_index_name": item["human_readable_index_name"],
                "epoch_request_time": item["epoch_request_time"],
                "status": item["status"],
                "percent_complete": item["percent_complete"],
            })

    # exit if no 'scheduled' jobs were found
    if not job_metadata:
        print("No jobs found")
        exit()
    # convert to dataframe for easier processing
    df = pd.DataFrame(job_metadata)
    # jobs should be run in the order they were requested - sort by epoch_request_time
    df.sort_values(by="epoch_request_time", ascending=True, inplace=True)
    index_to_schedule = df.iloc[0]["human_readable_index_name"]
    print(f"Scheduling job for index: {index_to_schedule}")
    schedule_indexing_job(index_to_schedule)


if __name__ == "__main__":
    main()
