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
        # check if report_id exists in the index
        if not report_table["community"].isin([report_id]).any():
            raise ValueError(f"Report '{report_id}' not found in index '{index_name}'.")
        # check if multiple reports with the same id exist (should not happen)
        if len(report_table.loc[report_table["community"] == report_id]) > 1:
            raise ValueError(
                f"Multiple reports with id '{report_id}' found in index '{index_name}'."
            )
        report_content = report_table.loc[
            report_table["community"] == report_id, "full_content"
        ].to_numpy()[0]
        return ReportResponse(text=report_content)
    except Exception:
        logger = LoggerSingleton().get_instance()
        logger.on_error("Could not get report.")
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
        text_units = pd.read_parquet(
            f"abfs://{sanitized_index_name}/{TEXT_UNITS_TABLE}",
            storage_options=get_pandas_storage_options(),
        )
        docs = pd.read_parquet(
            f"abfs://{sanitized_index_name}/{DOCUMENTS_TABLE}",
            storage_options=get_pandas_storage_options(),
        )
        # rename columns for easy joining
        docs = docs[["id", "title"]].rename(
            columns={"id": "document_id", "title": "source_document"}
        )
        # explode the 'document_ids' column so the format matches with 'document_id'
        text_units = text_units.explode("document_ids")

        # verify that text_unit_id exists in the index
        if not text_units["chunk_id"].isin([text_unit_id]).any():
            raise ValueError(
                f"Text unit '{text_unit_id}' not found in index '{index_name}'."
            )

        # combine tables to create a (chunk_id -> source_document) mapping
        merged_table = text_units.merge(
            docs, left_on="document_ids", right_on="document_id", how="left"
        )
        row = merged_table.loc[
            merged_table["chunk_id"] == text_unit_id, ["chunk", "source_document"]
        ]
        return TextUnitResponse(
            text=row["chunk"].to_numpy()[0],
            source_document=row["source_document"].to_numpy()[0],
        )
    except Exception:
        logger = LoggerSingleton().get_instance()
        logger.on_error("Could not get text chunk.")
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
        # check if entity_id exists in the index
        if not entity_table["human_readable_id"].isin([entity_id]).any():
            raise ValueError(f"Entity '{entity_id}' not found in index '{index_name}'.")
        row = entity_table[entity_table["human_readable_id"] == entity_id]
        return EntityResponse(
            name=row["name"].to_numpy()[0],
            description=row["description"].to_numpy()[0],
            text_units=row["text_unit_ids"].to_numpy()[0].tolist(),
        )
    except Exception:
        logger = LoggerSingleton().get_instance()
        logger.on_error("Could not get entity")
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
        logger = LoggerSingleton().get_instance()
        logger.on_error("Could not get claim.")
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
        logger = LoggerSingleton().get_instance()
        logger.on_error("Could not get relationship.")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving relationship '{relationship_id}' from index '{index_name}'.",
        )
