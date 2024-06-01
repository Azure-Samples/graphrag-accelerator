# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import hashlib
import logging
import time

# from dataclasses import asdict
from typing import (
    Any,
    Dict,
    Optional,
)

from datashaper.workflow.workflow_callbacks import NoopWorkflowCallbacks
from opencensus.ext.azure.log_exporter import AzureLogHandler


class ApplicationInsightsWorkflowCallbacks(NoopWorkflowCallbacks):
    """A reporter that writes to an AppInsights Workspace."""

    def __init__(
        self,
        connection_string: str,
        logger_name: str | None = None,
        logger_level: int = logging.INFO,
        properties: Dict[str, Any] = {},
    ):
        """
        Initialize the AppInsightsReporter.

        Args:
            connection_string (str): The connection string for the App Insights instance.
            logger_name (str | None, optional): The name of the logger. Defaults to None.
            logger_level (int, optional): The logging level. Defaults to logging.INFO.
            properties (Dict[str, Any], optional): Additional properties to be included in the log. Defaults to {}.
        """
        self._logger: logging.Logger
        self._logger_name = logger_name
        self._logger_level = logger_level
        self._logger_level_name: str = logging.getLevelName(logger_level)
        self._properties = properties

        self._workflow_name = "N/A"

        """Create a new logger with an AppInsights handler."""
        self.__init_logger(connection_string=connection_string)

    def __init_logger(self, connection_string, max_logger_init_retries: int = 10):
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
                # Set up Azure Monitor
                self._logger.addHandler(
                    AzureLogHandler(connection_string=connection_string)
                )
                # Set the logging level to INFO
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

        return {"custom_dimensions": {**self._properties, **unwrap_dict(details)}}

    def on_workflow_start(self, name: str, instance: object) -> None:
        """Execute this callback when a workflow starts."""
        self._workflow_name = name

        message = f"Workflow {name} started."
        details = {
            "workflow_name": name,
            "workflow_instance": str(instance),
        }
        self._logger.info(
            message, stack_info=False, extra=self._format_details(details=details)
        )

    def on_workflow_end(self, name: str, instance: object) -> None:
        """Execute this callback when a workflow ends."""
        message = f"Workflow {name} completed."
        details = {
            "workflow_name": name,
            "workflow_instance": str(instance),
        }
        self._logger.info(
            message, stack_info=False, extra=self._format_details(details=details)
        )

    def on_error(
        self,
        message: str,
        cause: Optional[BaseException] = None,
        stack: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> None:
        """A call back handler for when an error occurs."""
        details = {} if details is None else details
        details = {"cause": cause, "stack": stack, **details}
        self._logger.error(
            message, stack_info=True, extra=self._format_details(details=details)
        )

    def on_warning(self, message: str, details: Optional[dict] = None) -> None:
        """A call back handler for when a warning occurs."""
        self._logger.warning(
            message, stack_info=False, extra=self._format_details(details=details)
        )

    def on_log(self, message: str, details: Optional[dict] = None) -> None:
        """A call back handler for when a log message occurs."""
        self._logger.info(
            message, stack_info=False, extra=self._format_details(details=details)
        )

    def on_measure(
        self, name: str, value: float, details: Optional[dict] = None
    ) -> None:
        """A call back handler for when a measurement occurs."""
        pass


def unwrap_dict(input_dict, parent_key="", sep="_"):
    """
    Recursively unwraps a nested dictionary by flattening it into a single-level dictionary.

    Args:
        input_dict (dict): The input dictionary to be unwrapped.
        parent_key (str, optional): The parent key to be prepended to the keys of the unwrapped dictionary. Defaults to ''.
        sep (str, optional): The separator to be used between the parent key and the child key. Defaults to '_'.

    Returns:
        dict: The unwrapped dictionary.
    """
    items = []
    for k, v in input_dict.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(unwrap_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)
