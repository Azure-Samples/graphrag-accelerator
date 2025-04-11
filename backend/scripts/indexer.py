# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import argparse
import asyncio
import traceback
from pathlib import Path

import graphrag.api as api
from graphrag.callbacks.workflow_callbacks import WorkflowCallbacks

# from graphrag.index.create_pipeline_config import create_pipeline_config
from graphrag.config.enums import IndexingMethod
from graphrag.config.load_config import load_config
from graphrag.config.models.graph_rag_config import GraphRagConfig
from graphrag.index.typing.pipeline_run_result import PipelineRunResult
from graphrag.index.workflows.factory import PipelineFactory

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
    ROOT_DIR = Path(__file__).resolve().parent / "settings.yaml"
    config: GraphRagConfig = load_config(
        root_dir=ROOT_DIR.parent, 
        config_filepath=ROOT_DIR
    )
    # dynamically assign the sanitized index name 
    config.vector_store["default_vector_store"].container_name = sanitized_index_name

    # dynamically set indexing storage values
    config.input.container_name = sanitized_storage_name
    config.output.container_name = sanitized_index_name
    config.reporting.container_name = sanitized_index_name
    config.cache.container_name = sanitized_index_name
    
    # update extraction prompts
    PROMPT_DIR = Path(__file__).resolve().parent

    # set prompt for entity extraction / graph construction
    if pipeline_job.entity_extraction_prompt is None:
        # use the default prompt
        config.extract_graph.prompt = None
    else:
        # try to load the custom prompt
        fname = "extract_graph.txt"
        with open(PROMPT_DIR / fname, "w") as file:
            file.write(pipeline_job.entity_extraction_prompt)
        config.extract_graph.prompt = fname

    # set prompt for entity summarization
    if pipeline_job.entity_summarization_prompt is None:
        # use the default prompt
        config.summarize_descriptions.prompt = None
    else:
        # try to load the custom prompt
        fname = "summarize_descriptions.txt"
        with open(PROMPT_DIR / fname, "w") as file:
            file.write(pipeline_job.entity_summarization_prompt)
        config.summarize_descriptions.prompt = fname

    # set prompt for community graph summarization
    if pipeline_job.community_summarization_graph_prompt is None:
        # use the default prompt
        config.community_reports.graph_prompt = None
    else:
        # try to load the custom prompt
        fname = "community_report_graph.txt"
        with open(PROMPT_DIR / fname, "w") as file:
            file.write(pipeline_job.community_summarization_graph_prompt)
        pipeline_job.community_summarization_graph_prompt = fname

    # set prompt for community text summarization
    if pipeline_job.community_summarization_text_prompt is None:
        # use the default prompt
        config.community_reports.text_prompt = None
    else:
        fname = "community_report_text.txt"
        # try to load the custom prompt
        with open(PROMPT_DIR / fname, "w") as file:
            file.write(pipeline_job.community_summarization_text_prompt)
        config.community_reports.text_prompt = fname

    # set the extraction strategy
    indexing_method = IndexingMethod(pipeline_job.indexing_method)
    pipeline_workflows = PipelineFactory.create_pipeline(config, indexing_method)

    # reset pipeline job details
    pipeline_job.status = PipelineJobState.RUNNING

    pipeline_job.all_workflows = pipeline_workflows.names()
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
                config=config,
                method=indexing_method,
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
