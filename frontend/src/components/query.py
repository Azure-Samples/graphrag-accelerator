# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from typing import Literal

import numpy as np
import pandas as pd
import requests
import streamlit as st

from src.graphrag_api import GraphragAPI


class GraphQuery:
    KILOBYTE = 1024

    def __init__(self, client: GraphragAPI):
        self.client = client

    def search(
        self,
        query_type: Literal["Global Streaming", "Local Streaming", "Global", "Local"],
        search_index: str | list[str],
        query: str,
    ) -> None:
        idler_message_list = [
            "Querying the graph...",
            "Processing the query...",
            "The graph is working hard...",
            "Fetching the results...",
            "Reticulating splines...",
            "Almost there...",
            "The report format is customizable, for this demo we report back in executive summary format. It's prompt driven to change as you like!",
            "Just a few more seconds...",
            "You probably know these messages are just for fun...",
            "In the meantime, here's a fun fact: Did you know that the Microsoft GraphRAG Copilot is built on top of the Microsoft GraphRAG Solution Accelerator?",
            "The average graph query processes several textbooks worth of information to get you your answer.  I hope it was a good question!",
            "Shamelessly buying time...",
            "When the answer comes, make sure to check the context reports, the detail there is incredible!",
            "When we ingest data into the graph, the structure of language itself is used to create the graph structure. It's like a language-based neural network, using neural networks to understand language to network. It's a network-ception!",
            "The answers will come eventually, I promise.  In the meantime, I recommend a doppio espresso, or a nice cup of tea.  Or both!  The GraphRAG team runs on caffeine.",
            "The graph is a complex structure, but it's working hard to get you the answer you need.",
            "GraphRAG is step one in a long journey of understanding the world through language.  It's a big step, but there's so much more to come.",
            "The results are on their way...",
        ]

        message = np.random.choice(idler_message_list)
        with st.spinner(text=message):
            try:
                match query_type:
                    case "Global Streaming":
                        _ = self.global_streaming_search(search_index, query)
                    case "Local Streaming":
                        _ = self.local_streaming_search(search_index, query)
                    case "Global":
                        _ = self.global_search(search_index, query)
                    case "Local":
                        _ = self.local_search(search_index, query)

            except requests.exceptions.RequestException as e:
                st.error(f"Error with query {query_type}: {str(e)}")

    def global_streaming_search(
        self, search_index: str | list[str], query: str
    ) -> None:
        """
        Executes a global streaming query on the specified index.
        Handles the response and displays the results in the Streamlit app.
        """
        query_response = self.client.global_streaming_query(search_index, query)
        assistant_response = ""
        context_list = []

        if query_response.status_code == 200:
            text_placeholder = st.empty()
            for chunk in query_response.iter_lines(
                # allow up to 256KB to avoid excessive many reads
                chunk_size=256 * GraphQuery.KILOBYTE,
                decode_unicode=True,
            ):
                try:
                    payload = json.loads(chunk)
                except json.JSONDecodeError as e:
                    # In the event that a chunk is not a complete JSON object,
                    # document it for further analysis.
                    print(chunk)
                    raise e

                token = payload["token"]
                context = payload["context"]
                if (token != "<EOM>") and (context is None):
                    assistant_response += token
                    text_placeholder.write(assistant_response)
                elif (token == "<EOM>") and (context is not None):
                    context_list.append(context)

            if not assistant_response:
                st.write(
                    self.format_md_text(
                        "Not enough contextual data to support your query: No results found.\tTry another query.",
                        "red",
                        True,
                    )
                )
                return
            else:
                with self._create_section_expander("Query Context"):
                    st.write(
                        self.format_md_text(
                            "Double-click on content to expand text", "red", False
                        )
                    )
                    self._build_st_dataframe(
                        context_list[0]["reports"], drop_columns=[]
                    )
        else:
            print(query_response.reason, query_response.content)
            raise Exception("Received unexpected response from server")

    def local_streaming_search(self, search_index: str | list[str], query: str) -> None:
        """
        Executes a local streaming query on the specified index.
        Handles the response and displays the results in the Streamlit app.
        """
        query_response = self.client.local_streaming_query(search_index, query)
        assistant_response = ""
        context_list = []

        if query_response.status_code == 200:
            text_placeholder = st.empty()
            for chunk in query_response.iter_lines(
                # allow up to 256KB to avoid excessive many reads
                chunk_size=256 * GraphQuery.KILOBYTE,
                decode_unicode=True,
            ):
                try:
                    payload = json.loads(chunk)
                except json.JSONDecodeError as e:
                    # In the event that a chunk is not a complete JSON object,
                    # document it for further analysis.
                    print(chunk)
                    raise e

                token = payload["token"]
                context = payload["context"]
                if (token != "<EOM>") and (context is None):
                    assistant_response += token
                    text_placeholder.write(assistant_response)
                elif (token == "<EOM>") and (context is not None):
                    context_list.append(context)

            if not assistant_response:
                st.write(
                    self.format_md_text(
                        "Not enough contextual data to support your query: No results found.\tTry another query.",
                        "red",
                        True,
                    )
                )
                return
            else:
                with self._create_section_expander("Query Context"):
                    st.write(
                        self.format_md_text(
                            "Double-click on content to expand text", "red", False
                        )
                    )
                    self._build_st_dataframe(
                        context_list[0]["reports"], drop_columns=[]
                    )
                    self._build_st_dataframe(
                        context_list[0]["entities"], drop_columns=[]
                    )
                    self._build_st_dataframe(
                        context_list[0]["relationships"], drop_columns=[]
                    )
                    self._build_st_dataframe(
                        context_list[0]["sources"], drop_columns=[]
                    )
        else:
            print(query_response.reason, query_response.content)
            raise Exception("Received unexpected response from server")

    def global_search(self, search_index: str | list[str], query: str) -> None:
        query_response = self.client.query_index(
            index_name=search_index, query_type="Global", query=query
        )
        if query_response["result"] != "":
            with self._create_section_expander("Query Response", "black", True, True):
                st.write(query_response["result"])
            with self._create_section_expander("Query Context"):
                st.write(
                    self.format_md_text(
                        "Double-click on content to expand text", "red", False
                    )
                )
                self._build_st_dataframe(query_response["context_data"]["reports"])

    def local_search(self, search_index: str | list[str], query: str) -> None:
        query_response = self.client.query_index(
            index_name=search_index, query_type="Local", query=query
        )
        results = query_response["result"]
        if results != "":
            with self._create_section_expander("Query Response", "black", True, True):
                st.write(results)

        context_data = query_response["context_data"]
        reports = context_data["reports"]
        entities = context_data["entities"]
        relationships = context_data["relationships"]
        # sources = context_data["sources"]

        if any(reports):
            with self._create_section_expander("Query Context"):
                st.write(
                    self.format_md_text(
                        "Double-click on content to expand text", "red", False
                    )
                )
                self._build_st_dataframe(reports)

        if any(entities):
            with st.spinner("Loading context entities..."):
                with self._create_section_expander("Context Entities"):
                    df_entities = pd.DataFrame(entities)
                    self._build_st_dataframe(df_entities, entity_df=True)

                # TODO: Fix the next portion of code to provide a more granular entity view
                # for report in entities:
                #     entity_response = get_source_entity(
                #         report["index_name"], report["id"], self.api_url, self.headers
                #     )
                #     for unit in entity_response["text_units"]:
                #         response = requests.get(
                #             f"{self.api_url}/source/text/{report['index_name']}/{unit}",
                #             headers=self.headers,
                #         )
                #         text_info = response.json()
                #         if text_info is not None:
                #             with st.expander(
                #                 f" Entity: {report['entity']} - Source Document: {text_info['source_document']} "
                #             ):
                #                 st.write(text_info["text"])

        if any(relationships):
            with st.spinner("Loading context relationships..."):
                with self._create_section_expander("Context Relationships"):
                    df_relationships = pd.DataFrame(relationships)
                    self._build_st_dataframe(df_relationships, rel_df=True)

                    # TODO: Fix the next portion of code to provide a more granular relationship view
                    # for report in query_response["context_data"][
                    #     "relationships"
                    # ][:15]:
                    #     # with st.expander(
                    #     #     f"Source: {report['source']} Target: {report['target']} Rank: {report['rank']}"
                    #     # ):
                    #     # st.write(report["description"])
                    #     relationship_data = requests.get(
                    #         f"{self.api_url}/source/relationship/{report['index_name']}/{report['id']}",
                    #         headers=self.headers,
                    #     )
                    #     relationship_data = relationship_data.json()
                    #     for unit in relationship_data["text_units"]:
                    #         response = requests.get(
                    #             f"{self.api_url}/source/text/{report['index_name']}/{unit}",
                    #             headers=self.headers,
                    #         )
                    #         text_info_rel = response.json()
                    #         df_textinfo_rel = pd.DataFrame([text_info_rel])
                    #         with st.expander(
                    #             f"Source: {report['source']} Target: {report['target']} - Source Document: {sources['source_document']} "
                    #         ):
                    #             st.write(sources["text"])
                    #             st.dataframe(
                    #                 df_textinfo_rel, use_container_width=True
                    #             )

    def _build_st_dataframe(
        self,
        data: dict | pd.DataFrame,
        drop_columns: list[str] = ["id", "index_id", "index_name", "in_context"],
        entity_df: bool = False,
        rel_df: bool = False,
    ) -> st.dataframe:  # type: ignore
        df_context = (
            data if isinstance(data, pd.DataFrame) else pd.DataFrame.from_records(data)
        )
        if any(drop_columns):
            df_context.drop(columns=drop_columns, inplace=True, axis=1, errors="ignore")
        if entity_df:
            return st.dataframe(
                df_context,
                use_container_width=True,
                column_config={
                    "entity": "Entity",
                    "description": "Description",
                    "number of relationships": "Number of Relationships",
                },
            )
        if rel_df:
            return st.dataframe(
                df_context,
                use_container_width=True,
                column_config={
                    "source": "Source",
                    "target": "Target",
                    "description": "Description",
                    "weight": "Weight",
                    "rank": "Rank",
                    "links": "Links",
                },
            )
        return st.dataframe(
            df_context,
            use_container_width=True,
            column_config={
                "title": "Report Title",
                "content": "Report Content",
                "rank": "Rank",
            },
        )

    def format_md_text(self, text: str, color: str, bold: bool) -> str:
        """
        Formats text for display in Streamlit app using Markdown syntax.
        """
        if bold:
            return f":{color}[**{text}**]"
        return f":{color}[{text}]"

    def _create_section_expander(
        self, title: str, color: str = "blue", bold: bool = True, expanded: bool = False
    ) -> st.expander:  # type: ignore
        """
        Creates an expander in the Streamlit app with the specified title and content.
        """
        return st.expander(self.format_md_text(title, color, bold), expanded=expanded)
