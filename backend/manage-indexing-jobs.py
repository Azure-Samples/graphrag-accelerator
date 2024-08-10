# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
A naive implementation of a job manager that leverages k8s CronJob and CosmosDB
to schedule graphrag indexing jobs in a first-come-first-serve manner (based on epoch time).
"""

import os

import pandas as pd
import yaml
from kubernetes import (
    client,
    config,
)
from src.api.azure_clients import AzureStorageClientManager
from src.api.common import sanitize_name
from src.models import PipelineJob
from src.reporting.reporter_singleton import ReporterSingleton
from src.typing.pipeline import PipelineJobState


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
    except Exception:
        reporter = ReporterSingleton().get_instance()
        reporter.on_error(
            "Index job manager encountered error scheduling indexing job",
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
    # NOTE: this file location is relative to the WORKDIR set in Dockerfile-backend
    with open("indexing-job-template.yaml", "r") as f:
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


def main():
    azure_storage_client_manager = AzureStorageClientManager()
    job_container_store_client = (
        azure_storage_client_manager.get_cosmos_container_client(
            database_name="graphrag", container_name="jobs"
        )
    )
    # retrieve status for all jobs that are either scheduled or running
    job_metadata = []
    for item in job_container_store_client.read_all_items():
        # exit if a job is running
        if item["status"] == PipelineJobState.RUNNING.value:
            print(
                f"Indexing job for '{item['human_readable_index_name']}' already running. Will not schedule another. Exiting..."
            )
            exit()
        if item["status"] == PipelineJobState.SCHEDULED.value:
            job_metadata.append(
                {
                    "human_readable_index_name": item["human_readable_index_name"],
                    "epoch_request_time": item["epoch_request_time"],
                    "status": item["status"],
                    "percent_complete": item["percent_complete"],
                }
            )
    # exit if no jobs found
    if not job_metadata:
        print("No jobs found")
        exit()
    # convert to dataframe for easy processing
    df = pd.DataFrame(job_metadata)
    # jobs are run in the order they were requested - sort by epoch_request_time
    df.sort_values(by="epoch_request_time", ascending=True, inplace=True)
    index_to_schedule = df.iloc[0]["human_readable_index_name"]
    print(f"Scheduling job for index: {index_to_schedule}")
    schedule_indexing_job(index_to_schedule)


if __name__ == "__main__":
    main()
