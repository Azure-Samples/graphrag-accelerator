# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import hashlib
import logging
import sys
import time
from typing import (
    Any,
    Dict,
    Optional,
)

from graphrag.callbacks.noop_workflow_callbacks import NoopWorkflowCallbacks


class ConsoleWorkflowCallbacks(NoopWorkflowCallbacks):
    """A reporter that writes to a stream (sys.stdout)."""

    _logger: logging.Logger
    _logger_name: str
    _logger_level: int
    _logger_level_name: str
    _properties: Dict[str, Any]
    _workflow_name: str
    _index_name: str
    _num_workflow_steps: int
    _processed_workflow_steps: list[str] = []

    def __init__(
        self,
        logger_name: str | None = None,
        logger_level: int = logging.INFO,
        index_name: str = "",
        num_workflow_steps: int = 0,
        properties: Dict[str, Any] = {},
    ):
        """
        Initialize the ConsoleWorkflowCallbacks.

        Args:
            logger_name (str | None, optional): The name of the logger. Defaults to None.
            logger_level (int, optional): The logging level. Defaults to logging.INFO.
            index_name (str, optional): The name of an index. Defaults to "".
            num_workflow_steps (int): A list of workflow names ordered by their execution. Defaults to [].
            properties (Dict[str, Any], optional): Additional properties to be included in the log. Defaults to {}.
        """
        self._logger: logging.Logger
        self._logger_name = logger_name
        self._logger_level = logger_level
        self._logger_level_name: str = logging.getLevelName(logger_level)
        self._properties = properties
        self._workflow_name = "N/A"
        self._index_name = index_name
        self._num_workflow_steps = num_workflow_steps
        self._processed_workflow_steps = []  # maintain a running list of workflow steps that get processed
        """Create a new logger with an AppInsights handler."""
        self.__init_logger()

    def __init_logger(self, max_logger_init_retries: int = 10):
        max_retry = max_logger_init_retries
        while not (hasattr(self, "_logger")):
            if max_retry == 0:
                raise Exception(
                    "Failed to create logger. Could not disambiguate logger name."
                )

            # generate a unique logger name
            current_time = str(time.time())
            unique_hash = hashlib.sha256(current_time.encode()).hexdigest()
            self._logger_name = f"{self.__class__.__name__}-{unique_hash}"
            if self._logger_name not in logging.Logger.manager.loggerDict:
                # instantiate new logger
                self._logger = logging.getLogger(self._logger_name)
                self._logger.propagate = False
                # remove any existing handlers
                self._logger.handlers.clear()
                # create a console handler
                handler = logging.StreamHandler(stream=sys.stdout)
                # create a formatter and include 'extra_details' in the format string
                handler.setFormatter(
                    # logging.Formatter(
                    #     "[%(levelname)s] %(asctime)s - %(message)s \n %(stack)s"
                    # )
                    logging.Formatter("[%(levelname)s] %(asctime)s - %(message)s")
                )
                self._logger.addHandler(handler)
                # set logging level
                self._logger.setLevel(logging.INFO)

            # reduce sentinel counter value
            max_retry -= 1

    def _format_details(self, details: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """
        Format the details dictionary to comply with the Application Insights structured.

        logging Property column standard.

        Args:
            details (Dict[str, Any] | None): Optional dictionary containing additional details to log.

        Returns:
            Dict[str, Any]: The formatted details dictionary with custom dimensions.
        """
        if not isinstance(details, dict) or (details is None):
            details = {}
        return {**self._properties, **details}

    def workflow_start(self, name: str, instance: object) -> None:
        """Execute this callback when a workflow starts."""
        self._workflow_name = name
        self._processed_workflow_steps.append(name)
        message = f"Index: {self._index_name} -- " if self._index_name else ""
        workflow_progress = (
            f" ({len(self._processed_workflow_steps)}/{self._num_workflow_steps})"
            if self._num_workflow_steps
            else ""
        )  # will take the form "(1/4)"
        message += f"Workflow{workflow_progress}: {name} started."
        details = {
            "workflow_name": name,
            # "workflow_instance": str(instance),
        }
        if self._index_name:
            details["index_name"] = self._index_name
        self._logger.info(
            message, stack_info=False, extra=self._format_details(details=details)
        )

    def workflow_end(self, name: str, instance: object) -> None:
        """Execute this callback when a workflow ends."""
        message = f"Index: {self._index_name} -- " if self._index_name else ""
        workflow_progress = (
            f" ({len(self._processed_workflow_steps)}/{self._num_workflow_steps})"
            if self._num_workflow_steps
            else ""
        )  # will take the form "(1/4)"
        message += f"Workflow{workflow_progress}: {name} complete."
        details = {
            "workflow_name": name,
            # "workflow_instance": str(instance),
        }
        if self._index_name:
            details["index_name"] = self._index_name
        self._logger.info(
            message, stack_info=False, extra=self._format_details(details=details)
        )

    def error(
        self,
        message: str,
        cause: Optional[BaseException] = None,
        stack: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> None:
        """A call back handler for when an error occurs."""
        details = {} if details is None else details
        details = {"cause": str(cause), "stack": stack, **details}
        self._logger.error(
            message,
            exc_info=True,
            stack_info=False,
            extra=self._format_details(details=details),
        )

    def warning(self, message: str, details: Optional[dict] = None) -> None:
        """A call back handler for when a warning occurs."""
        self._logger.warning(
            message, stack_info=False, extra=self._format_details(details=details)
        )

    def log(self, message: str, details: Optional[dict] = None) -> None:
        """A call back handler for when a log message occurs."""
        self._logger.info(
            message, stack_info=False, extra=self._format_details(details=details)
        )
