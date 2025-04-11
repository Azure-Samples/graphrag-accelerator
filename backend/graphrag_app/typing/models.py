# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from io import StringIO
from typing import (
    Any,
    List,
    Optional,
)

import pandas as pd
from graphrag.callbacks.query_callbacks import QueryCallbacks
from pydantic import BaseModel


class BaseResponse(BaseModel):
    status: str


class ClaimResponse(BaseModel):
    covariate_type: str
    type: str
    description: str
    subject_id: str
    object_id: str
    source_text: str
    text_unit_id: str
    document_ids: List[str]


class EntityResponse(BaseModel):
    name: str
    type: str
    description: str
    text_units: list[int]


class IndexingConfigs(BaseModel):
    index_name: str


class GraphRequest(IndexingConfigs):
    index_name: str
    query: str
    community_level: int | None = None
    response_type: str = "Multiple Paragraphs"


class GraphGlobalRequest(GraphRequest):
    dynamic_community_selection: bool = False


class GraphLocalRequest(GraphRequest):
    conversation_history_max_turns: int = 5


class GraphDriftRequest(GraphRequest):
    conversation_history_max_turns: int = 5


class GraphResponse(BaseModel):
    result: Any
    context_data: Any


class GraphDataResponse(BaseModel):
    nodes: int
    edges: int


class IndexNameList(BaseModel):
    index_name: List[str]


class IndexStatusResponse(BaseModel):
    status_code: int
    index_name: str
    storage_name: str
    status: str
    percent_complete: float
    progress: str


class ReportResponse(BaseModel):
    text: str


class RelationshipResponse(BaseModel):
    source: str
    source_id: int
    target: str
    target_id: int
    description: str
    text_units: list[int]


class QueryData(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    communities: pd.DataFrame
    community_reports: pd.DataFrame
    entities: pd.DataFrame
    text_units: Optional[pd.DataFrame] = None
    relationships: Optional[pd.DataFrame] = None
    covariates: Optional[pd.DataFrame] = None
    community_level: Optional[int] = 1
    config: Optional[Any] = None


class StreamingCallback(QueryCallbacks):
    context: Optional[Any] = None
    response: Optional[StringIO] = StringIO()

    def on_context(self, context) -> None:
        """Handle when context data is constructed."""
        super().on_context(context)
        self.context = context

    def on_llm_new_token(self, token) -> None:
        """Handle when a new token is generated."""
        super().on_llm_new_token(token)
        self.response.write(token)


class StorageNameList(BaseModel):
    storage_name: List[str]


class TextUnitResponse(BaseModel):
    text_unit_id: int
    text: str
    source_document: str
    source_document_id: int
