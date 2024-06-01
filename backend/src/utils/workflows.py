# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import List

from graphrag.index.config import PipelineWorkflowReference


def remove_step_from_workflow(
    workflow: PipelineWorkflowReference, step_names: str | List[str]
) -> List[PipelineWorkflowReference]:
    if isinstance(step_names, str):
        step_names = [step_names]
    return [step for step in workflow.steps if step.get("verb") not in step_names]
