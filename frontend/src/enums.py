# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from enum import Enum


class PromptKeys(str, Enum):
    ENTITY = "entity_extraction"
    SUMMARY = "summarize_descriptions"
    COMMUNITY = "community_report"


class PromptFileNames(str, Enum):
    ENTITY = "entity_extraction_prompt.txt"
    SUMMARY = "summarize_descriptions_prompt.txt"
    COMMUNITY = "community_report_prompt.txt"


class PromptTextAreas(str, Enum):
    ENTITY = "entity_text_area"
    SUMMARY = "summary_text_area"
    COMMUNITY = "community_text_area"


class StorageIndexVars(str, Enum):
    SELECTED_STORAGE = "selected_storage"
    INPUT_STORAGE = "input_storage"
    SELECTED_INDEX = "selected_index"


class EnvVars(str, Enum):
    APIM_SUBSCRIPTION_KEY = "APIM_SUBSCRIPTION_KEY"
    DEPLOYMENT_URL = "DEPLOYMENT_URL"
