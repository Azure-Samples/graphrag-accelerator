# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
import os
from dataclasses import dataclass
from typing import Any, List

import tiktoken
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from graphrag.config import GraphRagConfig
from graphrag.model import (
    CommunityReport,
    Covariate,
    Entity,
    Relationship,
    TextUnit,
)
from graphrag.model.types import TextEmbedder
from graphrag.query.context_builder.entity_extraction import EntityVectorStoreKey
from graphrag.query.input.loaders.dfs import (
    read_community_reports,
    read_covariates,
    read_entities,
    read_relationships,
    read_text_units,
)
from graphrag.query.input.retrieval.relationships import (
    calculate_relationship_combined_rank,
)
from graphrag.query.llm.oai.chat_openai import ChatOpenAI
from graphrag.query.llm.oai.embedding import OpenAIEmbedding
from graphrag.query.llm.oai.typing import OpenaiApiType
from graphrag.query.structured_search.local_search.mixed_context import (
    LocalSearchMixedContext,
)
from graphrag.query.structured_search.local_search.search import LocalSearch
from graphrag.vector_stores.base import (
    BaseVectorStore,
    VectorStoreDocument,
    VectorStoreSearchResult,
)

cognitive_services_endpoint = os.environ.get(
    "GRAPHRAG_COGNITIVE_SERVICES_ENDPOINT",
    "https://cognitiveservices.azure.com/.default",
)
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), cognitive_services_endpoint
)


@dataclass
class CommunityData:
    reports: List[CommunityReport]
    entities: List[Entity]
    relationships: List[Relationship]
    text_units: List[TextUnit]
    covariates: List[Covariate]


class CommunitySearchHelpers:
    def __init__(self, index_names: str | List[str], config: GraphRagConfig):
        self.llm = ChatOpenAI(
            azure_ad_token_provider=token_provider,
            api_base=config.llm.api_base,
            model=config.llm.model,
            api_type=OpenaiApiType.AzureOpenAI,
            deployment_name=config.llm.deployment_name,
            api_version=config.llm.api_version,
            max_retries=config.llm.max_retries,
        )

        if isinstance(index_names, str):
            index_names = [index_names]

        self.token_encoder = tiktoken.model.encoding_for_model(config.llm.model)

        self.text_embedder = OpenAIEmbedding(
            azure_ad_token_provider=token_provider,
            api_base=config.embeddings.llm.api_base,
            api_type=OpenaiApiType.AzureOpenAI,
            model=config.embeddings.llm.model,
            deployment_name=config.embeddings.llm.deployment_name,
            api_version=config.embeddings.llm.api_version,
            max_retries=config.embeddings.llm.max_retries,
        )

        self.context_builder_params = {
            "use_community_summary": False,  # False means using full community reports. True means using community short summaries.
            "shuffle_data": True,
            "include_community_rank": True,
            "min_community_rank": 0,
            "max_tokens": config.global_search.max_tokens,
            "context_name": "Reports",
        }

        self.local_context_params = {
            "text_unit_prop": config.local_search.text_unit_prop,
            "community_prop": config.local_search.community_prop,
            "conversation_history_max_turns": config.local_search.conversation_history_max_turns,
            "conversation_history_user_turns_only": True,
            "top_k_mapped_entities": config.local_search.top_k_entities,
            "top_k_relationships": config.local_search.top_k_relationships,
            "include_entity_rank": True,
            "include_relationship_weight": True,
            "include_community_rank": False,
            "return_candidate_context": False,
            "embedding_vectorstore_key": EntityVectorStoreKey.ID,  # set this to EntityVectorStoreKey.TITLE if the vectorstore uses entity title as ids
            "max_tokens": config.local_search.max_tokens,  # change this based on the token limit you have on your model (if you are using a model with 8k limit, a good setting could be 5000)
        }

        self.llm_params = {
            "max_tokens": config.local_search.llm_max_tokens,
            "temperature": 0.0,
        }

        self.description_embedding_store = self._get_embedding_description_store(
            collection_names=[
                f"{index_name}_description_embedding" for index_name in index_names
            ]
        )

    def read_community_info(
        self,
        report_df,
        entity_df,
        edges_df,
        covariate_df,
        text_unit_df,
    ):
        entities = read_entities(
            df=entity_df,
            id_col="id",
            title_col="title",
            type_col="type",
            short_id_col="short_id",
            description_col="description",
            community_col="community_ids",
            rank_col="rank",
            name_embedding_col=None,
            description_embedding_col="description_embedding",
            graph_embedding_col=None,
            text_unit_ids_col="text_unit_ids",
            document_ids_col=None,
        )

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

        relationships = read_relationships(
            df=edges_df,
            id_col="id",
            short_id_col="short_id",
            source_col="source",
            target_col="target",
            description_col="description",
            weight_col="weight",
            description_embedding_col=None,
            text_unit_ids_col="text_unit_ids",
            document_ids_col=None,
        )
        relationships = calculate_relationship_combined_rank(
            relationships=relationships, entities=entities, ranking_attribute="rank"
        )

        if covariate_df:
            claims = read_covariates(
                df=covariate_df,
                id_col="id",
                short_id_col="short_id",
                subject_col="subject_id",
                subject_type_col=None,
                covariate_type_col="covariate_type",
                attributes_cols=[
                    "object_id",
                    "status",
                    "start_date",
                    "end_date",
                    "description",
                ],
                text_unit_ids_col=None,
                document_ids_col=None,
            )
        else:
            claims = {}
        covariates = {"claims": claims}

        text_units = read_text_units(
            df=text_unit_df,
            id_col="id",
            short_id_col=None,
            text_col="text",
            embedding_col=None,
            entities_col=None,
            relationships_col=None,
            covariates_col=None,
        )

        return CommunityData(
            reports=reports,
            entities=entities,
            relationships=relationships,
            text_units=text_units,
            covariates=covariates,
        )

    def _get_embedding_description_store(self, collection_names: List[str]):
        ai_search_url = os.environ["AI_SEARCH_URL"]
        description_embedding_store = MultiAzureAISearch(
            collection_name="multi",
            document_collection=None,
            db_connection=None,
        )
        description_embedding_store.connect(url=ai_search_url)
        for collection_name in collection_names:
            description_embedding_store.add_collection(collection_name)
        return description_embedding_store

    def get_search_engine(self, community_data):
        context_builder = LocalSearchMixedContext(
            community_reports=community_data.reports,
            text_units=community_data.text_units,
            entities=community_data.entities,
            relationships=community_data.relationships,
            covariates=community_data.covariates,
            entity_text_embeddings=self.description_embedding_store,
            embedding_vectorstore_key=EntityVectorStoreKey.ID,  # if the vectorstore uses entity title as ids, set this to EntityVectorStoreKey.TITLE
            text_embedder=self.text_embedder,
            token_encoder=self.token_encoder,
        )
        search_engine = LocalSearch(
            llm=self.llm,
            context_builder=context_builder,
            token_encoder=self.token_encoder,
            llm_params=self.llm_params,
            context_builder_params=self.local_context_params,
            response_type="single-page report",  # free form text describing the response type and format, can be anything, e.g. prioritized list, single paragraph, multiple paragraphs, multiple-page report
        )
        return search_engine


class MultiAzureAISearch(BaseVectorStore):
    """The Azure AI Search vector storage implementation."""

    def __init__(
        self,
        collection_name: str,
        db_connection: Any,
        document_collection: Any,
        query_filter: Any | None = None,
        **kwargs: Any,
    ):
        self.collection_name = collection_name
        self.db_connection = db_connection
        self.document_collection = document_collection
        self.query_filter = query_filter
        self.kwargs = kwargs
        self.collections = []

    def add_collection(self, collection_name: str):
        self.collections.append(collection_name)

    def connect(self, **kwargs: Any) -> Any:
        """Connect to the AzureAI vector store."""
        self.url = kwargs.get("url", None)
        self.vector_size = kwargs.get("vector_size", 1536)

        self.vector_search_profile_name = kwargs.get(
            "vector_search_profile_name", "vectorSearchProfile"
        )

        if self.url:
            pass
        else:
            not_supported_error = (
                "Azure AI Search client is not supported on local host."
            )
            raise ValueError(not_supported_error)

    def load_documents(
        self, documents: list[VectorStoreDocument], overwrite: bool = True
    ) -> None:
        raise NotImplementedError("load_documents() method not implemented")

    def filter_by_id(self, include_ids: list[str] | list[int]) -> Any:
        """Build a query filter to filter documents by a list of ids."""
        if include_ids is None or len(include_ids) == 0:
            self.query_filter = None
            # returning to keep consistency with other methods, but not needed
            return self.query_filter

        # more info about odata filtering here: https://learn.microsoft.com/en-us/azure/search/search-query-odata-search-in-function
        # search.in is faster that joined and/or conditions
        id_filter = ",".join([f"{id!s}" for id in include_ids])
        self.query_filter = f"search.in(id, '{id_filter}', ',')"

        # returning to keep consistency with other methods, but not needed
        # TODO: Refactor on a future PR
        return self.query_filter

    def similarity_search_by_vector(
        self, query_embedding: list[float], k: int = 10, **kwargs: Any
    ) -> list[VectorStoreSearchResult]:
        """Perform a vector-based similarity search."""
        vectorized_query = VectorizedQuery(
            vector=query_embedding, k_nearest_neighbors=k, fields="vector"
        )

        docs = []
        for collection_idx, collection_name in enumerate(self.collections):
            add_on = "-" + str(collection_idx)
            db_connection = SearchClient(
                self.url, collection_name, DefaultAzureCredential()
            )
            response = db_connection.search(
                vector_queries=[vectorized_query],
            )
            mod_response = []
            for r in response:
                r["id"] = r.get("id", "") + add_on
                mod_response += [r]
            docs += mod_response
        return [
            VectorStoreSearchResult(
                document=VectorStoreDocument(
                    id=doc.get("id", ""),
                    text=doc.get("text", ""),
                    vector=doc.get("vector", []),
                    attributes=(json.loads(doc.get("attributes", "{}"))),
                ),
                score=abs(doc["@search.score"]),
            )
            for doc in docs
        ]

    def similarity_search_by_text(
        self, text: str, text_embedder: TextEmbedder, k: int = 10, **kwargs: Any
    ) -> list[VectorStoreSearchResult]:
        """Perform a text-based similarity search."""
        query_embedding = text_embedder(text)
        if query_embedding:
            return self.similarity_search_by_vector(
                query_embedding=query_embedding, k=k
            )
        return []
