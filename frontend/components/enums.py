from enum import Enum


class PromptKeys(Enum):
    SUMMARY = "summarize_descriptions"
    ENTITY = "entity_extraction"
    COMMUNITY = "community_report"


class StorageIndexVars(Enum):
    SELECTED_STORAGE = "selected_storage"
    INPUT_STORAGE = "input_storage"
    SELECTED_INDEX = "selected_index"
