# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
from urllib.parse import urlparse

import requests
from datashaper import NoopWorkflowCallbacks, WorkflowCallbacks

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


def send_webhook(
    url: str,
    summary: str,
    title: str,
    subtitle: str,
    index_name: str,
    note: str,
    job_status: str,
    reporter: NoopWorkflowCallbacks | None = None,
) -> bool:
    if _is_valid_url(url):
        try:
            payload = {
                "@type": "MessageCard",
                "@context": "http://schema.org/extensions",
                "themeColor": "0076D7",
                "summary": summary,
                "sections": [
                    {
                        "activityTitle": f"**{title}**",
                        "activitySubtitle": subtitle,
                        "facts": [
                            {"name": "Index Name", "value": index_name},
                            {"name": "Note", "value": note},
                            {"name": "Status", "value": job_status},
                        ],
                        "markdown": True,
                    }
                ],
            }
            requests.post(url, json=payload)
        except Exception as e:
            if reporter is not None:
                reporter.on_warning(f"Error sending webhook: {e}", details=payload)
            return False
    return True


def _is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False
