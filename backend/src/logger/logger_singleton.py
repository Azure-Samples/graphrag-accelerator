# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.


from graphrag.callbacks.workflow_callbacks import WorkflowCallbacks

from src.logger.load_logger import load_pipeline_logger
from src.logger.typing import Logger


class LoggerSingleton:
    _instance: WorkflowCallbacks = None

    @classmethod
    def get_instance(cls) -> WorkflowCallbacks:
        if not cls._instance:
            reporters = []
            for logger_type in ["BLOB", "CONSOLE", "APP_INSIGHTS"]:
                reporters.append(Logger[logger_type])
            cls._instance = load_pipeline_logger(logging_dir="", loggers=reporters)
        return cls._instance
