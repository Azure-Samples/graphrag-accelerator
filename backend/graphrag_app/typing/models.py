# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import (
    Any,
    List,
)

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
    description: str
    text_units: list[str]


class GraphRequest(BaseModel):
    index_name: str
    query: str
    community_level: int | None = None


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
    text_units: list[str]


class StorageNameList(BaseModel):
    storage_name: List[str]


class TextUnitResponse(BaseModel):
    text: str
    source_document: str
