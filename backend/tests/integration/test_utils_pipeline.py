# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""
Integration tests for the PipelineJob class.
"""

from typing import Generator

import pytest

from graphrag_app.typing.pipeline import PipelineJobState
from graphrag_app.utils.pipeline import PipelineJob


@pytest.fixture()
def cosmos_index_job_entry(cosmos_client) -> Generator[str, None, None]:
    """Create an entry for an indexing job in the appropriate CosmosDB database and container
    that graphrag expects when first scheduling an indexing job."""

    db_client = cosmos_client.get_database_client("graphrag")
    container_client = db_client.get_container_client("jobs")
    synthetic_job_entry = {
        "id": "testID",
        "epoch_request_time": 0,
        "human_readable_index_name": "test_human_readable_index_name",
        "sanitized_index_name": "test_sanitized_index_name",
        "human_readable_storage_name": "test_human_readable_storage_name",
        "sanitized_storage_name": "test_sanitized_storage_name",
        "all_workflows": ["workflow1", "workflow2"],
        "completed_workflows": ["workflow1"],
        "failed_workflows": ["workflow2"],
        "status": PipelineJobState.COMPLETE,
        "percent_complete": 50.0,
        "progress": "some progress",
    }
    container_client.upsert_item(synthetic_job_entry)
    yield synthetic_job_entry["id"]
    # teardown
    container_client.delete_item(
        synthetic_job_entry["id"], partition_key=synthetic_job_entry["id"]
    )


def test_pipeline_job_interface(cosmos_index_job_entry):
    """Test the graphrag_app.utils.pipeline.PipelineJob class interface."""
    pipeline_job = PipelineJob()

    # test creating a new entry
    pipeline_job.create_item(
        id="synthetic_id",
        human_readable_index_name="test_human_readable_index_name",
        human_readable_storage_name="test_human_readable_storage_name",
        entity_extraction_prompt="fake entity extraction prompt",
        community_report_prompt="fake community report prompt",
        summarize_descriptions_prompt="fake summarize descriptions prompt",
    )
    assert pipeline_job.item_exist("synthetic_id")

    # test loading an existing entry
    pipeline_job = pipeline_job.load_item(cosmos_index_job_entry)
    assert pipeline_job.id == "testID"
    assert pipeline_job.human_readable_index_name == "test_human_readable_index_name"
    assert pipeline_job.sanitized_index_name == "test_sanitized_index_name"
    assert (
        pipeline_job.human_readable_storage_name == "test_human_readable_storage_name"
    )
    assert pipeline_job.sanitized_storage_name == "test_sanitized_storage_name"
    assert pipeline_job.all_workflows == ["workflow1", "workflow2"]
    assert pipeline_job.completed_workflows == ["workflow1"]
    assert pipeline_job.failed_workflows == ["workflow2"]
    assert pipeline_job.status == PipelineJobState.COMPLETE
    assert pipeline_job.percent_complete == 50.0
    assert pipeline_job.progress == "some progress"
    assert pipeline_job.calculate_percent_complete() == 50.0

    # test setters and getters
    pipeline_job.id = "newID"
    assert pipeline_job.id == "newID"
    pipeline_job.epoch_request_time = 1
    assert pipeline_job.epoch_request_time == 1

    pipeline_job.human_readable_index_name = "new_human_readable_index_name"
    assert pipeline_job.human_readable_index_name == "new_human_readable_index_name"
    pipeline_job.sanitized_index_name = "new_sanitized_index_name"
    assert pipeline_job.sanitized_index_name == "new_sanitized_index_name"

    pipeline_job.human_readable_storage_name = "new_human_readable_storage_name"
    assert pipeline_job.human_readable_storage_name == "new_human_readable_storage_name"
    pipeline_job.sanitized_storage_name = "new_sanitized_storage_name"
    assert pipeline_job.sanitized_storage_name == "new_sanitized_storage_name"

    pipeline_job.entity_extraction_prompt = "new_entity_extraction_prompt"
    assert pipeline_job.entity_extraction_prompt == "new_entity_extraction_prompt"
    pipeline_job.community_report_prompt = "new_community_report_prompt"
    assert pipeline_job.community_report_prompt == "new_community_report_prompt"
    pipeline_job.summarize_descriptions_prompt = "new_summarize_descriptions_prompt"
    assert (
        pipeline_job.summarize_descriptions_prompt
        == "new_summarize_descriptions_prompt"
    )

    pipeline_job.all_workflows = ["new_workflow1", "new_workflow2", "new_workflow3"]
    assert len(pipeline_job.all_workflows) == 3

    pipeline_job.completed_workflows = ["new_workflow1", "new_workflow2"]
    assert len(pipeline_job.completed_workflows) == 2

    pipeline_job.failed_workflows = ["new_workflow3"]
    assert len(pipeline_job.failed_workflows) == 1
