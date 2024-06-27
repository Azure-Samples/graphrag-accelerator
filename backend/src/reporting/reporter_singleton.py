# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
from urllib.parse import urlparse

from datashaper import WorkflowCallbacks

from src.reporting.load_reporter import load_pipeline_reporter_from_list
from src.reporting.typing import Reporters


class ReporterSingleton:
    _instance: WorkflowCallbacks = None

    @classmethod
    def get_instance(cls) -> WorkflowCallbacks:
        if cls._instance is None:
            # Setting up reporters based on environment variable or defaults
            reporters = []
            for reporter_name in os.getenv(
                "REPORTERS", Reporters.CONSOLE.name.upper()
            ).split(","):
                try:
                    reporters.append(Reporters[reporter_name.upper()])
                except KeyError:
                    raise ValueError(f"Found unknown reporter: {reporter_name}")

            cls._instance = load_pipeline_reporter_from_list(
                reporting_dir="", reporters=reporters
            )
        return cls._instance


def _is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False
