# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os

import pandas as pd
from kubernetes import (
    client,
    config,
)
from src.api.azure_clients import AzureStorageClientManager
from src.api.index import _generate_aks_job_manifest
from src.reporting.reporter_singleton import ReporterSingleton
from src.typing.pipeline import PipelineJobState


def schedule_indexing_job(index_name: str):
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
        batch_v1 = client.BatchV1Api()
        batch_v1.create_namespaced_job(
            body=job_manifest, namespace=os.environ["AKS_NAMESPACE"]
        )
    except Exception:
        reporter = ReporterSingleton().get_instance()
        reporter.on_error("Index job manager encountered error scheduling indexing job",)

def main():
    azure_storage_client_manager = AzureStorageClientManager()
    job_container_store_client = azure_storage_client_manager.get_cosmos_container_client(
        database_name="graphrag", container_name="jobs"
    )
    # retrieve metadata about all jobs that are either scheduled or running
    job_metadata=[]
    for item in job_container_store_client.read_all_items():
        if item["status"] != PipelineJobState.SCHEDULED or item["status"] != PipelineJobState.RUNNING:
            job_metadata.append( {"human_readable_index_name":item["human_readable_index_name"],
                                "epoch_request_time":item["epoch_request_time"],
                                "status":item["status"],
                                "percent_complete":item["percent_complete"] } )
    # exit if no jobs found
    if not job_metadata:
        print("No jobs found")
        exit()
    # convert to dataframe for easy processing
    df = pd.DataFrame(job_metadata)
    # exit if a job is running
    if len(df[df["status"] == PipelineJobState.RUNNING.value]) > 0:
        print("Job already running")
        exit()
    # otherwise start the next indexing job
    # jobs are run in the order they were requested
    # sort by epoch_request_time
    df.sort_values(by="epoch_request_time", ascending=True, inplace=True)
    index_to_schedule = df.iloc[0]["human_readable_index_name"]
    print(f"Scheduling job for index: {index_to_schedule}")
    schedule_indexing_job(index_to_schedule)

if __name__ == "__main__":
    main()
