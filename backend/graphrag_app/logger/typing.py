# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import logging
from enum import Enum
from typing import Literal

from graphrag.logger.base import StatusLogger
from pydantic import Field as pydantic_Field


class Logger(Enum):
    BLOB = (1, "blob")
    CONSOLE = (2, "console")
    FILE = (3, "file")
    APP_INSIGHTS = (4, "app_insights")


class PipelineAppInsightsLogger(StatusLogger):
    """Represents the ApplicationInsights reporting configuration for the pipeline."""

    type: Literal["app_insights"] = Logger.APP_INSIGHTS.name.lower()
    """The type of reporting."""

    connection_string: str = pydantic_Field(
        description="The connection string for the App Insights instance.",
        default=None,
    )
    """The connection string for the App Insights instance."""

    logger_name: str = pydantic_Field(
        description="The name for logger instance", default=None
    )
    """The name for logger instance"""

    logger_level: int = pydantic_Field(
        description="The name of the logger. Defaults to None.", default=logging.INFO
    )
    """The name of the logger. Defaults to None."""


# add the new type to the existing PipelineReportingConfigTypes
# StatusLogger = (
#     StatusLogger | PipelineAppInsightsReportingConfig
# )
