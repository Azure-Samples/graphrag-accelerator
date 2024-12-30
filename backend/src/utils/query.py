# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import pandas as pd
from graphrag.query.indexer_adapters import (
    read_indexer_covariates,
    read_indexer_entities,
    read_indexer_relationships,
    read_indexer_reports,
    read_indexer_text_units,
)

from src.api.common import get_pandas_storage_options


def get_entities(
    entity_table_path: str,
    entity_embedding_table_path: str,
    community_level: int = 0,
) -> pd.DataFrame:
    storage_options = get_pandas_storage_options()
    entity_df = pd.read_parquet(
        entity_table_path,
        storage_options=storage_options,
    )
    entity_embedding_df = pd.read_parquet(
        entity_embedding_table_path,
        storage_options=storage_options,
    )
    return pd.DataFrame(
        read_indexer_entities(entity_df, entity_embedding_df, community_level)
    )


def get_reports(
    entity_table_path: str, community_report_table_path: str, community_level: int
) -> pd.DataFrame:
    storage_options = get_pandas_storage_options()
    entity_df = pd.read_parquet(
        entity_table_path,
        storage_options=storage_options(),
    )
    report_df = pd.read_parquet(
        community_report_table_path,
        storage_options=storage_options(),
    )
    return pd.DataFrame(read_indexer_reports(report_df, entity_df, community_level))


def get_relationships(relationships_table_path: str) -> pd.DataFrame:
    relationship_df = pd.read_parquet(
        relationships_table_path,
        storage_options=get_pandas_storage_options(),
    )
    return pd.DataFrame(read_indexer_relationships(relationship_df))


def get_covariates(covariate_table_path: str) -> pd.DataFrame:
    covariate_df = pd.read_parquet(
        covariate_table_path,
        storage_options=get_pandas_storage_options(),
    )
    return pd.DataFrame(read_indexer_covariates(covariate_df))


def get_text_units(text_unit_table_path: str) -> pd.DataFrame:
    text_unit_df = pd.read_parquet(
        text_unit_table_path,
        storage_options=get_pandas_storage_options(),
    )
    return pd.DataFrame(read_indexer_text_units(text_unit_df))


def get_df(
    table_path: str,
) -> pd.DataFrame:
    df = pd.read_parquet(
        table_path,
        storage_options=get_pandas_storage_options(),
    )
    return df
