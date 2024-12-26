# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.


import pandas as pd
from fastapi import APIRouter, HTTPException

from src.api.common import (
    get_pandas_storage_options,
    sanitize_name,
    validate_index_file_exist,
)
from src.logger import LoggerSingleton
from src.models import (
    ClaimResponse,
    EntityResponse,
    RelationshipResponse,
    ReportResponse,
    TextUnitResponse,
)

source_route = APIRouter(
    prefix="/source",
    tags=["Sources"],
)


COMMUNITY_REPORT_TABLE = "output/create_final_community_reports.parquet"
COVARIATES_TABLE = "output/create_final_covariates.parquet"
ENTITY_EMBEDDING_TABLE = "output/create_final_entities.parquet"
RELATIONSHIPS_TABLE = "output/create_final_relationships.parquet"
TEXT_UNITS_TABLE = "output/create_base_text_units.parquet"
DOCUMENTS_TABLE = "output/create_base_documents.parquet"


@source_route.get(
    "/report/{index_name}/{report_id}",
    summary="Return a single community report.",
    response_model=ReportResponse,
    responses={200: {"model": ReportResponse}},
)
async def get_report_info(index_name: str, report_id: str):
    # check for existence of file the query relies on to validate the index is complete
    sanitized_index_name = sanitize_name(index_name)
    validate_index_file_exist(sanitized_index_name, COMMUNITY_REPORT_TABLE)
    try:
        report_table = pd.read_parquet(
            f"abfs://{sanitized_index_name}/{COMMUNITY_REPORT_TABLE}",
            storage_options=get_pandas_storage_options(),
        )
        # row = report_table[report_table["community"] == report_id]
        # return ReportResponse(text=row["full_content"].values[0])
        report_content = report_table.loc[
            report_table["community"] == report_id, "full_content"
        ][0]
        return ReportResponse(text=report_content)
    except Exception:
        reporter = LoggerSingleton().get_instance()
        reporter.on_error("Could not get report.")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving report '{report_id}' from index '{index_name}'.",
        )


@source_route.get(
    "/text/{index_name}/{text_unit_id}",
    summary="Return a single base text unit.",
    response_model=TextUnitResponse,
    responses={200: {"model": TextUnitResponse}},
)
async def get_chunk_info(index_name: str, text_unit_id: str):
    # check for existence of file the query relies on to validate the index is complete
    sanitized_index_name = sanitize_name(index_name)
    validate_index_file_exist(sanitized_index_name, TEXT_UNITS_TABLE)
    validate_index_file_exist(sanitized_index_name, DOCUMENTS_TABLE)
    try:
        text_unit_table = pd.read_parquet(
            f"abfs://{sanitized_index_name}/{TEXT_UNITS_TABLE}",
            storage_options=get_pandas_storage_options(),
        )
        docs = pd.read_parquet(
            f"abfs://{sanitized_index_name}/{DOCUMENTS_TABLE}",
            storage_options=get_pandas_storage_options(),
        )
        links = {
            el["id"]: el["title"]
            for el in docs[["id", "title"]].to_dict(orient="records")
        }
        text_unit_table["source_doc"] = text_unit_table["document_ids"].apply(
            lambda x: links[x[0]]
        )
        row = text_unit_table.loc[
            text_unit_table.chunk_id == text_unit_id, ["chunk", "source_doc"]
        ]
        return TextUnitResponse(
            text=row["chunk"].values[0], source_document=row["source_doc"].values[0]
        )
    except Exception:
        reporter = LoggerSingleton().get_instance()
        reporter.on_error("Could not get text chunk.")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving text chunk '{text_unit_id}' from index '{index_name}'.",
        )


@source_route.get(
    "/entity/{index_name}/{entity_id}",
    summary="Return a single entity.",
    response_model=EntityResponse,
    responses={200: {"model": EntityResponse}},
)
async def get_entity_info(index_name: str, entity_id: int):
    # check for existence of file the query relies on to validate the index is complete
    sanitized_index_name = sanitize_name(index_name)
    validate_index_file_exist(sanitized_index_name, ENTITY_EMBEDDING_TABLE)
    try:
        entity_table = pd.read_parquet(
            f"abfs://{sanitized_index_name}/{ENTITY_EMBEDDING_TABLE}",
            storage_options=get_pandas_storage_options(),
        )
        row = entity_table[entity_table.human_readable_id == entity_id]
        return EntityResponse(
            name=row["name"].values[0],
            description=row["description"].values[0],
            text_units=row["text_unit_ids"].values[0].tolist(),
        )
    except Exception:
        reporter = LoggerSingleton().get_instance()
        reporter.on_error("Could not get entity")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving entity '{entity_id}' from index '{index_name}'.",
        )


@source_route.get(
    "/claim/{index_name}/{claim_id}",
    summary="Return a single claim.",
    response_model=ClaimResponse,
    responses={200: {"model": ClaimResponse}},
)
async def get_claim_info(index_name: str, claim_id: int):
    # check for existence of file the query relies on to validate the index is complete
    # claims is optional in graphrag
    sanitized_index_name = sanitize_name(index_name)
    try:
        validate_index_file_exist(sanitized_index_name, COVARIATES_TABLE)
    except ValueError:
        raise HTTPException(
            status_code=500,
            detail=f"Claim data unavailable for index '{index_name}'.",
        )
    try:
        claims_table = pd.read_parquet(
            f"abfs://{sanitized_index_name}/{COVARIATES_TABLE}",
            storage_options=get_pandas_storage_options(),
        )
        claims_table.human_readable_id = claims_table.human_readable_id.astype(
            float
        ).astype(int)
        row = claims_table[claims_table.human_readable_id == claim_id]
        return ClaimResponse(
            covariate_type=row["covariate_type"].values[0],
            type=row["type"].values[0],
            description=row["description"].values[0],
            subject_id=row["subject_id"].values[0],
            object_id=row["object_id"].values[0],
            source_text=row["source_text"].values[0],
            text_unit_id=row["text_unit_id"].values[0],
            document_ids=row["document_ids"].values[0].tolist(),
        )
    except Exception:
        reporter = LoggerSingleton().get_instance()
        reporter.on_error("Could not get claim.")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving claim '{claim_id}' from index '{index_name}'.",
        )


@source_route.get(
    "/relationship/{index_name}/{relationship_id}",
    summary="Return a single relationship.",
    response_model=RelationshipResponse,
    responses={200: {"model": RelationshipResponse}},
)
async def get_relationship_info(index_name: str, relationship_id: int):
    # check for existence of file the query relies on to validate the index is complete
    sanitized_index_name = sanitize_name(index_name)
    validate_index_file_exist(sanitized_index_name, RELATIONSHIPS_TABLE)
    validate_index_file_exist(sanitized_index_name, ENTITY_EMBEDDING_TABLE)
    try:
        relationship_table = pd.read_parquet(
            f"abfs://{sanitized_index_name}/{RELATIONSHIPS_TABLE}",
            storage_options=get_pandas_storage_options(),
        )
        entity_table = pd.read_parquet(
            f"abfs://{sanitized_index_name}/{ENTITY_EMBEDDING_TABLE}",
            storage_options=get_pandas_storage_options(),
        )
        row = relationship_table[
            relationship_table.human_readable_id == str(relationship_id)
        ]
        return RelationshipResponse(
            source=row["source"].values[0],
            source_id=entity_table[
                entity_table.name == row["source"].values[0]
            ].human_readable_id.values[0],
            target=row["target"].values[0],
            target_id=entity_table[
                entity_table.name == row["target"].values[0]
            ].human_readable_id.values[0],
            description=row["description"].values[0],
            text_units=[
                x[0] for x in row["text_unit_ids"].to_list()
            ],  # extract text_unit_ids from a list of panda series
        )
    except Exception:
        reporter = LoggerSingleton().get_instance()
        reporter.on_error("Could not get relationship.")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving relationship '{relationship_id}' from index '{index_name}'.",
        )
