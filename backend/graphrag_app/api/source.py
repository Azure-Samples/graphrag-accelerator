# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import traceback

import pandas as pd
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from graphrag_app.logger.load_logger import load_pipeline_logger
from graphrag_app.typing.models import (
    ClaimResponse,
    EntityResponse,
    RelationshipResponse,
    ReportResponse,
    TextUnitResponse,
)
from graphrag_app.utils.common import (
    pandas_storage_options,
    sanitize_name,
    subscription_key_check,
    validate_index_file_exist,
)

source_route = APIRouter(
    prefix="/source",
    tags=["Sources"],
)

if os.getenv("KUBERNETES_SERVICE_HOST"):
    source_route.dependencies.append(Depends(subscription_key_check))

COMMUNITY_TABLE = "output/communities.parquet"
COMMUNITY_REPORT_TABLE = "output/community_reports.parquet"
COVARIATES_TABLE = "output/covariates.parquet"
ENTITIES_TABLE = "output/entities.parquet"
RELATIONSHIPS_TABLE = "output/relationships.parquet"
TEXT_UNITS_TABLE = "output/text_units.parquet"
DOCUMENTS_TABLE = "output/documents.parquet"


@source_route.get(
    "/report/{container_name}/{report_id}",
    summary="Return a single community report.",
    response_model=ReportResponse,
    responses={status.HTTP_200_OK: {"model": ReportResponse}},
)
async def get_report_info(
    report_id: int,
    container_name: str,
    sanitized_container_name: str = Depends(sanitize_name),
):
    # check for existence of file the query relies on to validate the index is complete
    validate_index_file_exist(sanitized_container_name, COMMUNITY_REPORT_TABLE)
    try:
        report_table = pd.read_parquet(
            f"abfs://{sanitized_container_name}/{COMMUNITY_REPORT_TABLE}",
            storage_options=pandas_storage_options(),
        )
        # check if report_id exists in the index
        if not report_table["human_readable_id"].isin([report_id]).any():
            raise ValueError(
                f"Report '{report_id}' not found in index '{container_name}'."
            )
        # check if multiple reports with the same id exist (should not happen)
        if len(report_table.loc[report_table["human_readable_id"] == report_id]) > 1:
            raise ValueError(
                f"Multiple reports with id '{report_id}' found in index '{container_name}'."
            )
        report_content = report_table.loc[
            report_table["human_readable_id"] == report_id, "full_content_json"
        ].to_numpy()[0]
        return ReportResponse(text=report_content)
    except Exception as e:
        logger = load_pipeline_logger()
        logger.error(
            message="Could not get report.",
            cause=e,
            stack=traceback.format_exc(),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving report '{report_id}' from index '{container_name}'.",
        )


@source_route.get(
    "/text/{container_name}/{text_unit_id}",
    summary="Return a single base text unit.",
    response_model=TextUnitResponse,
    responses={status.HTTP_200_OK: {"model": TextUnitResponse}},
)
async def get_chunk_info(
    text_unit_id: int,
    container_name: str,
    sanitized_container_name: str = Depends(sanitize_name),
):
    # check for existence of file the query relies on to validate the index is complete
    validate_index_file_exist(sanitized_container_name, TEXT_UNITS_TABLE)
    validate_index_file_exist(sanitized_container_name, DOCUMENTS_TABLE)
    try:
        text_units = pd.read_parquet(
            f"abfs://{sanitized_container_name}/{TEXT_UNITS_TABLE}",
            storage_options=pandas_storage_options(),
        )
        text_units_filter = text_units["human_readable_id"].isin([text_unit_id])

        # verify that text_unit_id exists in the index
        if not text_units_filter.any():
            raise ValueError(
                f"Text unit '{text_unit_id}' not found in index '{container_name}'."
            )

        # explode the 'document_ids' column so the format matches with 'document_id'
        text_units = text_units[text_units_filter].explode("document_ids")

        docs = pd.read_parquet(
            f"abfs://{sanitized_container_name}/{DOCUMENTS_TABLE}",
            storage_options=pandas_storage_options(),
        )
        # rename columns for easy joining
        docs = docs[
            [
                "id", "title", "human_readable_id"
            ]
        ].rename(
            columns={
                "id": "document_id", 
                "title": "source_document",
                "human_readable_id": "document_human_readable_id"
            }
        )

        # combine tables to create a (chunk_id -> source_document) mapping
        merged_table = text_units.merge(
            docs, left_on="document_ids", right_on="document_id", how="left"
        )
        row = merged_table.loc[
            merged_table["human_readable_id"] == text_unit_id, 
            [
                "text", 
                "source_document",
                "human_readable_id",
                "document_human_readable_id"
            ]
        ]
        return TextUnitResponse(
            text_unit_id=row["human_readable_id"].to_numpy()[0],
            source_document_id=row["document_human_readable_id"].to_numpy()[0],
            text=row["text"].to_numpy()[0],
            source_document=row["source_document"].to_numpy()[0],
        )
    except Exception as e:
        logger = load_pipeline_logger()
        logger.error(
            message="Could not get text chunk.",
            cause=e,
            stack=traceback.format_exc(),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving text chunk '{text_unit_id}' from index '{container_name}'.",
        )


@source_route.get(
    "/entity/{container_name}/{entity_id}",
    summary="Return a single entity.",
    response_model=EntityResponse,
    responses={status.HTTP_200_OK: {"model": EntityResponse}},
)
async def get_entity_info(
    entity_id: int,
    container_name: str,
    sanitized_container_name: str = Depends(sanitize_name),
):
    # check for existence of file the query relies on to validate the index is complete
    validate_index_file_exist(sanitized_container_name, ENTITIES_TABLE)
    try:
        entity_table = pd.read_parquet(
            f"abfs://{sanitized_container_name}/{ENTITIES_TABLE}",
            storage_options=pandas_storage_options(),
        )
        text_units = pd.read_parquet(
            f"abfs://{sanitized_container_name}/{TEXT_UNITS_TABLE}",
            storage_options=pandas_storage_options(),
        )
        # check if entity_id exists in the index
        if not entity_table["human_readable_id"].isin([entity_id]).any():
            raise ValueError(
                f"Entity '{entity_id}' not found in index '{container_name}'."
            )
        row = entity_table[entity_table["human_readable_id"] == entity_id]
        text_unit_human_readable_ids = text_units[
            text_units["id"].isin(row["text_unit_ids"].to_numpy()[0].tolist())
        ]["human_readable_id"].to_list()
        return EntityResponse(
            name=row["title"].to_numpy()[0],
            type=row["type"].to_numpy()[0],
            description=row["description"].to_numpy()[0],
            text_units=text_unit_human_readable_ids,
        )
    except Exception as e:
        logger = load_pipeline_logger()
        logger.error(
            message="Could not get entity",
            cause=e,
            stack=traceback.format_exc(),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving entity '{entity_id}' from index '{container_name}'.",
        )


@source_route.get(
    "/claim/{container_name}/{claim_id}",
    summary="Return a single claim.",
    response_model=ClaimResponse,
    responses={status.HTTP_200_OK: {"model": ClaimResponse}},
)
async def get_claim_info(
    claim_id: int,
    container_name: str,
    sanitized_container_name: str = Depends(sanitize_name),
):
    # check for existence of file the query relies on to validate the index is complete
    # claims is optional in graphrag
    try:
        validate_index_file_exist(sanitized_container_name, COVARIATES_TABLE)
    except ValueError:
        raise HTTPException(
            status_code=500,
            detail=f"Claim data unavailable for index '{container_name}'.",
        )
    try:
        claims_table = pd.read_parquet(
            f"abfs://{sanitized_container_name}/{COVARIATES_TABLE}",
            storage_options=pandas_storage_options(),
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
    except Exception as e:
        logger = load_pipeline_logger()
        logger.error(
            message="Could not get claim.", cause=e, stack=traceback.format_exc()
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving claim '{claim_id}' for index '{container_name}'.",
        )


@source_route.get(
    "/relationship/{container_name}/{relationship_id}",
    summary="Return a single relationship.",
    response_model=RelationshipResponse,
    responses={status.HTTP_200_OK: {"model": RelationshipResponse}},
)
async def get_relationship_info(
    relationship_id: int,
    container_name: str,
    sanitized_container_name: str = Depends(sanitize_name),
):
    # check for existence of file the query relies on to validate the index is complete
    validate_index_file_exist(sanitized_container_name, RELATIONSHIPS_TABLE)
    validate_index_file_exist(sanitized_container_name, ENTITIES_TABLE)
    try:
        relationship_table = pd.read_parquet(
            f"abfs://{sanitized_container_name}/{RELATIONSHIPS_TABLE}",
            storage_options=pandas_storage_options(),
        )
        relationship_table_row = relationship_table[
            relationship_table.human_readable_id == relationship_id
        ]

        entity_table = pd.read_parquet(
            f"abfs://{sanitized_container_name}/{ENTITIES_TABLE}",
            storage_options=pandas_storage_options(),
        )
        text_units = pd.read_parquet(
            f"abfs://{sanitized_container_name}/{TEXT_UNITS_TABLE}",
            storage_options=pandas_storage_options(),
        )
        text_unit_ids = text_units[text_units["id"].isin(
            relationship_table_row["text_unit_ids"].values[0]
        )]["human_readable_id"]
        return RelationshipResponse(
            source=relationship_table_row["source"].values[0],
            source_id=entity_table[
                entity_table.title == relationship_table_row["source"].values[0]
            ].human_readable_id.values[0],
            target=relationship_table_row["target"].values[0],
            target_id=entity_table[
                entity_table.title == relationship_table_row["target"].values[0]
            ].human_readable_id.values[0],
            description=relationship_table_row["description"].values[0],
            text_units=text_unit_ids.to_list(),  # extract text_unit_ids from a list of panda series
        )
    except Exception as e:
        logger = load_pipeline_logger()
        logger.error(
            message="Could not get relationship.", cause=e, stack=traceback.format_exc()
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving relationship '{relationship_id}' from index '{container_name}'.",
        )
