# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.


from graphrag.callbacks.workflow_callbacks import WorkflowCallbacks

from src.logger.load_logger import load_pipeline_logger


class LoggerSingleton:
    _instance: WorkflowCallbacks = None

    @classmethod
    def get_instance(cls) -> WorkflowCallbacks:
        if not cls._instance:
            cls._instance = load_pipeline_logger()
        return cls._instance
