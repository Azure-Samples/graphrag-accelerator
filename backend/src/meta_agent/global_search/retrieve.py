# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os

import pandas as pd
import tiktoken
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from graphrag.config import GraphRagConfig
from graphrag.query.input.loaders.dfs import read_community_reports
from graphrag.query.llm.oai.chat_openai import ChatOpenAI
from graphrag.query.llm.oai.typing import OpenaiApiType
from graphrag.query.structured_search.global_search.community_context import (
    GlobalCommunityContext,
)
from graphrag.query.structured_search.global_search.search import (
    GlobalSearch,
    GlobalSearchLLMCallback,
)

cognitive_services_endpoint = os.environ.get(
    "COGNITIVE_SERVICES_ENDPOINT", "https://cognitiveservices.azure.com/.default"
)
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), cognitive_services_endpoint
)


class GlobalSearchHelpers:
    def __init__(self, config: GraphRagConfig):
        self.config: GraphRagConfig = config

        self.llm = ChatOpenAI(
            azure_ad_token_provider=token_provider,
            api_base=config.llm.api_base,
            model=config.llm.model,
            api_type=OpenaiApiType.AzureOpenAI,
            deployment_name=config.llm.deployment_name,
            api_version=config.llm.api_version,
            max_retries=config.llm.max_retries,
        )

        self.token_encoder = tiktoken.model.encoding_for_model(config.llm.model)

        self.context_builder_params = {
            "use_community_summary": False,
            "shuffle_data": True,
            "include_community_rank": True,
            "min_community_rank": 0,
            "max_tokens": config.global_search.max_tokens,
            "context_name": "Reports",
        }

        self.map_llm_params = {
            "max_tokens": config.global_search.map_max_tokens,
            "temperature": 0.0,
        }

        self.reduce_llm_params = {
            "max_tokens": config.global_search.reduce_max_tokens,
            "temperature": 0.0,
        }

    def get_search_engine(
        self,
        report_df: pd.DataFrame,
        callbacks: list[GlobalSearchLLMCallback] | None = None,
    ) -> GlobalSearch:
        reports = read_community_reports(
            df=report_df,
            id_col="community_id",
            short_id_col="community_id",
            community_col="community_id",
            title_col="title",
            summary_col="summary",
            content_col="full_content",
            rank_col="rank",
            summary_embedding_col=None,
            content_embedding_col=None,
        )

        context_builder = GlobalCommunityContext(
            community_reports=reports,
            token_encoder=self.token_encoder,
        )

        search_engine = GlobalSearch(
            llm=self.llm,
            context_builder=context_builder,
            token_encoder=self.token_encoder,
            max_data_tokens=self.config.global_search.data_max_tokens,
            map_llm_params=self.map_llm_params,
            reduce_llm_params=self.reduce_llm_params,
            context_builder_params=self.context_builder_params,
            callbacks=callbacks,
            response_type="Multiple Paragraphs",  # free form text describing the response type and format, can be anything, e.g. prioritized list, single paragraph, multiple paragraphs, multiple-page report
        )

        return search_engine
