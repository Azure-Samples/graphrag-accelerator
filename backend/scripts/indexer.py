# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import argparse
import asyncio
import traceback
from pathlib import Path

import graphrag.api as api
import yaml
from graphrag.callbacks.workflow_callbacks import WorkflowCallbacks
from graphrag.config.create_graphrag_config import create_graphrag_config
from graphrag.index.create_pipeline_config import create_pipeline_config
from graphrag.index.typing import PipelineRunResult

from graphrag_app.logger import (
    PipelineJobUpdater,
    load_pipeline_logger,
)
from graphrag_app.typing.pipeline import PipelineJobState
from graphrag_app.utils.azure_clients import AzureClientManager
from graphrag_app.utils.common import get_cosmos_container_store_client, sanitize_name
from graphrag_app.utils.pipeline import PipelineJob


def start_indexing_job(index_name: str):
    print("Start indexing job...")
    # get sanitized name
    sanitized_index_name = sanitize_name(index_name)

    # update or create new item in container-store in cosmosDB
    azure_client_manager = AzureClientManager()
    blob_service_client = azure_client_manager.get_blob_service_client()
    if not blob_service_client.get_container_client(sanitized_index_name).exists():
        blob_service_client.create_container(sanitized_index_name)

    cosmos_container_client = get_cosmos_container_store_client()
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
    SCRIPT_DIR = Path(__file__).resolve().parent
    with (SCRIPT_DIR / "settings.yaml").open("r") as f:
        data = yaml.safe_load(f)
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

    # set prompt for entity summarization
    if pipeline_job.entity_summarization_prompt:
        fname = "entity-summarization-prompt.txt"
        with open(fname, "w") as outfile:
            outfile.write(pipeline_job.entity_summarization_prompt)
        data["summarize_descriptions"]["prompt"] = fname
    else:
        data.pop("summarize_descriptions")

    # set prompt for community summarization
    if pipeline_job.community_summarization_prompt:
        fname = "community-summarization-prompt.txt"
        with open(fname, "w") as outfile:
            outfile.write(pipeline_job.community_summarization_prompt)
        data["community_reports"]["prompt"] = fname
    else:
        data.pop("community_reports")

    # generate default graphrag config parameters and override with custom settings
    parameters = create_graphrag_config(data, ".")

    # reset pipeline job details
    pipeline_job.status = PipelineJobState.RUNNING
    pipeline_config = create_pipeline_config(parameters)
    pipeline_job.all_workflows = [
        workflow.name for workflow in pipeline_config.workflows
    ]
    pipeline_job.completed_workflows = []
    pipeline_job.failed_workflows = []

    # create new loggers/callbacks just for this job
    print("Creating generic loggers...")
    logger: WorkflowCallbacks = load_pipeline_logger(
        logging_dir=sanitized_index_name,
        index_name=index_name,
        num_workflow_steps=len(pipeline_job.all_workflows),
    )

    # create pipeline job updater to monitor job progress
    print("Creating pipeline job updater...")
    pipeline_job_updater = PipelineJobUpdater(pipeline_job)

    # run the pipeline
    try:
        print("Building index...")
        pipeline_results: list[PipelineRunResult] = asyncio.run(
            api.build_index(
                config=parameters,
                callbacks=[logger, pipeline_job_updater],
            )
        )

        # once indexing job is done, check if any pipeline steps failed
        for result in pipeline_results:
            if result.errors:
                pipeline_job.failed_workflows.append(result.workflow)
        print("Indexing complete")

        if len(pipeline_job.failed_workflows) > 0:
            print("Indexing pipeline encountered errors.")
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
        error_details = {
            "index": index_name,
            "storage_name": storage_name,
        }
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

    start_indexing_job(index_name=args.index_name)
