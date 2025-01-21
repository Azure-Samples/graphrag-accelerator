# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import argparse
import asyncio
import inspect
import os
import traceback

import graphrag.api as api
import yaml
from graphrag.callbacks.workflow_callbacks import WorkflowCallbacks
from graphrag.config.create_graphrag_config import create_graphrag_config
from graphrag.index.create_pipeline_config import create_pipeline_config

from src.api.azure_clients import AzureClientManager
from src.logger import (
    Logger,
    PipelineJobUpdater,
    load_pipeline_logger,
)
from src.typing.pipeline import PipelineJobState
from src.utils.common import sanitize_name
from src.utils.pipeline import PipelineJob


def start_indexing_job(index_name: str):
    print("Start indexing job...")
    # get sanitized name
    sanitized_index_name = sanitize_name(index_name)

    # update or create new item in container-store in cosmosDB
    azure_client_manager = AzureClientManager()
    blob_service_client = azure_client_manager.get_blob_service_client()
    if not blob_service_client.get_container_client(sanitized_index_name).exists():
        blob_service_client.create_container(sanitized_index_name)

    cosmos_container_client = azure_client_manager.get_cosmos_container_client(
        database="graphrag", container="container-store"
    )
    cosmos_container_client.upsert_item({
        "id": sanitized_index_name,
        "human_readable_name": index_name,
        "type": "index",
    })

    print("Initialize pipeline job...")
    pipelinejob = PipelineJob()
    pipeline_job = pipelinejob.load_item(sanitized_index_name)
    sanitized_storage_name = pipeline_job.sanitized_storage_name
    storage_name = pipeline_job.human_readable_index_name

    # load custom pipeline settings
    this_directory = os.path.dirname(
        os.path.abspath(inspect.getfile(inspect.currentframe()))
    )
    data = yaml.safe_load(open(f"{this_directory}/settings.yaml"))
    # dynamically set some values
    data["input"]["container_name"] = sanitized_storage_name
    data["storage"]["container_name"] = sanitized_index_name
    data["reporting"]["container_name"] = sanitized_index_name
    data["cache"]["container_name"] = sanitized_index_name
    if "vector_store" in data["embeddings"]:
        data["embeddings"]["vector_store"]["collection_name"] = (
            f"{sanitized_index_name}_description_embedding"
        )

    # set prompt for entity extraction
    if pipeline_job.entity_extraction_prompt:
        fname = "entity-extraction-prompt.txt"
        with open(fname, "w") as outfile:
            outfile.write(pipeline_job.entity_extraction_prompt)
        data["entity_extraction"]["prompt"] = fname
    else:
        data.pop("entity_extraction")

    # set prompt for summarize descriptions
    if pipeline_job.summarize_descriptions_prompt:
        fname = "summarize-descriptions-prompt.txt"
        with open(fname, "w") as outfile:
            outfile.write(pipeline_job.summarize_descriptions_prompt)
        data["summarize_descriptions"]["prompt"] = fname
    else:
        data.pop("summarize_descriptions")

    # set prompt for community report
    if pipeline_job.community_report_prompt:
        fname = "community-report-prompt.txt"
        with open(fname, "w") as outfile:
            outfile.write(pipeline_job.community_report_prompt)
        data["community_reports"]["prompt"] = fname
    else:
        data.pop("community_reports")

    # generate default graphrag config parameters and override with custom settings
    parameters = create_graphrag_config(data, ".")

    # reset pipeline job details
    pipeline_job.status = PipelineJobState.RUNNING
    pipeline_job.all_workflows = []
    pipeline_job.completed_workflows = []
    pipeline_job.failed_workflows = []
    pipeline_config = create_pipeline_config(parameters)
    for workflow in pipeline_config.workflows:
        pipeline_job.all_workflows.append(workflow.name)

    # create new loggers/callbacks just for this job
    logger_names = []
    for logger_type in ["BLOB", "CONSOLE", "APP_INSIGHTS"]:
        logger_names.append(Logger[logger_type.upper()])
    print("Creating generic loggers...")
    logger: WorkflowCallbacks = load_pipeline_logger(
        logging_dir=sanitized_index_name,
        index_name=index_name,
        num_workflow_steps=len(pipeline_job.all_workflows),
        loggers=logger_names,
    )

    # create pipeline job updater to monitor job progress
    print("Creating pipeline job updater...")
    pipeline_job_updater = PipelineJobUpdater(pipeline_job)

    # run the pipeline
    try:
        print("Building index...")
        asyncio.run(
            api.build_index(
                config=parameters,
                callbacks=[logger, pipeline_job_updater],
            )
        )
        print("Index building complete")
        # if job is done, check if any pipeline steps failed
        if len(pipeline_job.failed_workflows) > 0:
            print("Indexing pipeline encountered error.")
            pipeline_job.status = PipelineJobState.FAILED
            logger.error(
                message=f"Indexing pipeline encountered error for index'{index_name}'.",
                details={
                    "index": index_name,
                    "storage_name": storage_name,
                    "status_message": "indexing pipeline encountered error",
                },
            )
        else:
            print("Indexing pipeline complete.")
            # record the pipeline completion
            pipeline_job.status = PipelineJobState.COMPLETE
            pipeline_job.percent_complete = 100
            logger.log(
                message=f"Indexing pipeline complete for index'{index_name}'.",
                details={
                    "index": index_name,
                    "storage_name": storage_name,
                    "status_message": "indexing pipeline complete",
                },
            )
        pipeline_job.progress = (
            f"{len(pipeline_job.completed_workflows)} out of "
            f"{len(pipeline_job.all_workflows)} workflows completed successfully."
        )
        if pipeline_job.status == PipelineJobState.FAILED:
            exit(1)  # signal to AKS that indexing job failed
    except Exception as e:
        pipeline_job.status = PipelineJobState.FAILED
        # update failed state in cosmos db
        error_details = {
            "index": index_name,
            "storage_name": storage_name,
        }
        # log error in local index directory logs
        logger.error(
            message=f"Indexing pipeline failed for index '{index_name}'.",
            cause=e,
            stack=traceback.format_exc(),
            details=error_details,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build a graphrag index.")
    parser.add_argument("-i", "--index-name", required=True)
    args = parser.parse_args()

    asyncio.run(
        start_indexing_job(
            index_name=args.index_name,
        )
    )
