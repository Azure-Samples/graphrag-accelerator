import asyncio
import json
import time

import numpy as np
import pandas as pd
import requests
import streamlit as st

from .functions import get_source_entity, query_index, show_index_options
from .index_pipeline import IndexPipeline


def get_main_tab() -> None:
    """
    Displays content of Main Tab
    """

    url = "https://github.com/Azure-Samples/graphrag-accelerator/blob/main/TRANSPARENCY.md"
    content = f"""
    ##  Welcome to GraphRAG!
    Diving into complex information and uncovering semantic relationships utilizing generative AI has never been easier. Here's how you can get started with just a few clicks:
    - **INDEXING:** On the **Index** tab:
        1. Select or upload your data
        2. Configure the LLM prompts to your doamin
        3. Name your index and click "Build Index" to begin building a GraphRAG Index.
    - **QUERYING:** On the **Query** tab:
        1. Choose an existing index
        2. Specify the query type
        3. Hit "Enter" or click "Search" to view insights.

    [GraphRAG]({url}) combines the power of RAG with a Graph structure, giving you insights at your fingertips.
    """
    # Display text in the gray box
    st.markdown(content, unsafe_allow_html=False)


def get_index_tab(
    containers: dict,
    api_url: str,
    headers: dict,
    headers_upload: dict,
    indexes: list[str],
) -> None:
    """
    Displays content of Index tab
    """
    pipeline = IndexPipeline(containers, api_url, headers, headers_upload)
    pipeline.storage_data_step()
    pipeline.prompt_config_step()
    pipeline.build_index_step()
    pipeline.check_status_step()


def get_query_tab(api_url: str, headers: dict, indexes: list[str]) -> None:
    """
    Displays content of Query Tab
    """
    KILOBYTE = 1024
    col1, col2 = st.columns(2)
    with col1:
        query_type = st.selectbox(
            "Query Type",
            ["Global Streaming", "Global", "Local"],
            help="Select the query type - Each yeilds different results of specificity. Global queries focus on the entire graph structure. Local queries focus on a set of communities (subgraphs) in the graph that are more connected to each other than they are to the rest of the graph structure and can focus on very specific entities in the graph. Global streaming is a global query that displays results as they appear live.",
        )
    with col2:
        select_index_search = st.multiselect(
            label="Index",
            options=show_index_options(indexes),
            help="Select the index(es) to query. The selected index(es) must have a complete status in order to yield query results without error. Use Check Index Status to confirm status.",
        )
    col3, col4 = st.columns([0.8, 0.2])
    with col3:
        search_bar = st.text_input("Query", key="search-query")
    with col4:
        search_button = st.button("QUERY", type="primary")

    async def search_button_clicked():
        query_response = {}
        # container_placeholder.empty()

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

        query_response = None
        try:
            while query_response is None:
                for _ in range(3):
                    # wait 5 seconds
                    message = np.random.choice(idler_message_list)
                    with st.spinner(text=message):
                        time.sleep(5)

                if query_type == "Global" or query_type == "Local":
                    with st.spinner():
                        query_response = await query_index(
                            select_index_search,
                            query_type,
                            search_bar,
                            api_url,
                            headers,
                        )
                elif query_type == "Global Streaming":
                    with st.spinner():
                        url = f"{api_url}/experimental/query/global/streaming"
                        query_response = requests.post(
                            url,
                            json={
                                "index_name": select_index_search,
                                "query": search_bar,
                            },
                            headers=headers,
                            stream=True,
                        )
                        assistant_response = ""
                        context_list = []
                        if query_response.status_code == 200:
                            text_placeholder = st.empty()
                            reports_context_expander = None
                            for chunk in query_response.iter_lines(
                                # allow up to 256KB to avoid excessive many reads
                                chunk_size=256 * KILOBYTE,
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
                                elif (token == "<EOM>") and (context is None):
                                    # Message is over, you will not receive the context values
                                    reports_context_expander = st.expander(
                                        "Expand to see context reports"
                                    )
                                elif (token == "<EOM>") and (context is not None):
                                    context_list.append(context)
                                    with reports_context_expander:
                                        with st.expander(context["title"]):
                                            df_context = pd.DataFrame.from_dict(
                                                [context]
                                            )
                                            if "id" in df_context.columns:
                                                df_context = df_context.drop(
                                                    "id", axis=1
                                                )
                                            if "title" in df_context.columns:
                                                df_context = df_context.drop(
                                                    "title", axis=1
                                                )
                                            if "index_id" in df_context.columns:
                                                df_context = df_context.drop(
                                                    "index_id", axis=1
                                                )
                                            st.dataframe(
                                                df_context, use_container_width=True
                                            )
                                else:
                                    print(chunk)
                                    raise Exception(
                                        "Received unexpected response from server"
                                    )

            if query_type == "Global" or query_type == "Local":
                # container_placeholder.empty()

                if query_response["result"] != "":
                    with st.expander("Results", expanded=True):
                        st.write(query_response["result"])

                if query_response["context_data"]["reports"] != []:
                    with st.expander(
                        f"View context for this response from {query_type} method:"
                    ):
                        if query_type == "Local":
                            st.write(
                                query_response["context_data"]["reports"][0]["content"]
                            )
                        else:
                            df = pd.DataFrame(query_response["context_data"]["reports"])
                            if "index_name" in df.columns:
                                df = df.drop("index_name", axis=1)
                            if "index_id" in df.columns:
                                df = df.drop("index_id", axis=1)
                            st.dataframe(df, use_container_width=True)

                if query_response["context_data"]["entities"] != []:
                    with st.spinner("Loading context entities..."):
                        with st.expander("View context entities"):
                            df_entities = pd.DataFrame(
                                query_response["context_data"]["entities"]
                            )
                            if "in_context" in df_entities.columns:
                                df_entities = df_entities.drop("in_context", axis=1)
                            st.dataframe(df_entities, use_container_width=True)

                            for report in query_response["context_data"]["entities"]:
                                entity_data = get_source_entity(
                                    report["index_name"], report["id"], api_url, headers
                                )
                                for unit in entity_data["text_units"]:
                                    response = requests.get(
                                        f"{api_url}/source/text/{report['index_name']}/{unit}",
                                        headers=headers,
                                    )
                                    text_info = response.json()
                                    if text_info is not None:
                                        with st.expander(
                                            f" Entity: {report['entity']} - Source Document: {text_info['source_document']} "
                                        ):
                                            st.write(text_info["text"])

                if query_response["context_data"]["relationships"] != []:
                    with st.spinner("Loading context relationships..."):
                        with st.expander("View context relationships"):
                            df_relationships = pd.DataFrame(
                                query_response["context_data"]["relationships"]
                            )
                            if "in_context" in df_relationships.columns:
                                df_relationships = df_relationships.drop(
                                    "in_context", axis=1
                                )
                            st.dataframe(df_relationships, use_container_width=True)
                            for report in query_response["context_data"][
                                "relationships"
                            ][:15]:
                                # with st.expander(
                                #     f"Source: {report['source']} Target: {report['target']} Rank: {report['rank']}"
                                # ):
                                # st.write(report["description"])
                                relationship_data = requests.get(
                                    f"{api_url}/source/relationship/{report['index_name']}/{report['id']}",
                                    headers=headers,
                                )
                                relationship_data = relationship_data.json()
                                for unit in relationship_data["text_units"]:
                                    response = requests.get(
                                        f"{api_url}/source/text/{report['index_name']}/{unit}",
                                        headers=headers,
                                    )
                                    text_info_rel = response.json()

                                    df_textinfo_rel = pd.DataFrame([text_info_rel])
                                    with st.expander(
                                        f"Source: {report['source']} Target: {report['target']} - Source Document: {text_info['source_document']} "
                                    ):
                                        st.write(text_info["text"])
                                        st.dataframe(
                                            df_textinfo_rel, use_container_width=True
                                        )
        except requests.exceptions.RequestException as e:
            st.error(f"Error with query: {str(e)}")

    if search_button:
        asyncio.run(search_button_clicked())
