# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import asyncio
import json
import os
import time

import numpy as np
import pandas as pd
import requests
import streamlit as st
from app_utils.app_functions import (
    get_entity_data,
    get_indexes_data,
    get_source_entity,
    get_storage_data,
    query_index,
    show_index_options,
)
from components.sidebar import sidebar_layout
from dotenv import load_dotenv

load_dotenv()


headers = {
    "Ocp-Apim-Subscription-Key": os.environ["APIM_SUBSCRIPTION_KEY"],
    "Content-Type": "application/json",  # Include other headers as needed
}

headers_upload = {"Ocp-Apim-Subscription-Key": os.environ["APIM_SUBSCRIPTION_KEY"]}
st.set_page_config(initial_sidebar_state="expanded", layout="wide")
# API endpoint URL
api_url = os.environ["DEPLOYMENT_URL"]
input_storage_name = ""
select_storage_name = ""

with open("style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


KILOBYTE = 1024


async def app():
    # main entry point

    # Call the API and get data
    data = get_storage_data(api_url, headers)

    if "entity_config" not in st.session_state:
        st.session_state["entity_config"] = ["DEFAULT"] + get_entity_data(
            api_url, headers
        )["entity_configuration_name"]
    indexes = get_indexes_data(api_url, headers)
    # Check if data is retrieved successfully
    sidebar_layout(
        data=data,
        api_url=api_url,
        headers=headers,
        headers_upload=headers_upload,
        indexes=indexes,
    )

    st.title("Microsoft GraphRAG Copilot")

    col1, col2, col3, col4 = st.columns([0.4, 0.23, 0.22, 0.1])

    # image = Image.open("./static/Microsoft_logo.png")
    # logo = col1.image(image)

    search_bar = col1.text_input("Query")
    query_type = col2.selectbox(
        "Query Type",
        ["Global", "Local", "Global Streaming"],
        help="Select the query type - Each yeilds different results of specificity. Global queries focus on the entire graph structure. Local queries focus on a set of communities (subgraphs) in the graph that are more connected to each other than they are to the rest of the graph structure and can focus on very specific entities in the graph. Global streaming is a global query that displays results as they appear live.",
    )
    select_index_search = col3.multiselect(
        label="Index",
        options=show_index_options(indexes),
        help="Select the index(es) to query. The selected index(es) must have a complete status in order to yield query results without error. Use Check Index Status to confirm status.",
    )
    search_button = col4.button("Search")
    url = "https://github.com/Azure-Samples/graphrag-accelerator/blob/main/docs/TRANSPARENCY.md"
    content = f"""
    ##  Welcome to GraphRAG!
    Diving into complex information and uncovering semantic relationships utilizing generative AI has never been easier. Here's how you can get started with just a few clicks:
    - *Set Up:* In the left pane, select or upload your data storage, configure entities, and name your index to begin building an index.
    - *Explore:* On the query side, choose your index, specify the query type, and click search to see insights.

    [GraphRAG]({url}) turns complex data tasks into a breeze, giving you insights at your fingertips.
    """
    # Display text in the gray box
    container_placeholder = st.markdown(content, unsafe_allow_html=False)

    deployer_email = os.environ.get("DEPLOYER_EMAIL", "deployer@email.com")
    footer = f"""
        <div class="footer">
            <p> Responses may be inaccurate; please review all responses for accuracy. Learn more about Azure OpenAI code of conduct <a href="https://learn.microsoft.com/en-us/legal/cognitive-services/openai/code-of-conduct"> here</a>. </br> For feedback, email us at <a href="mailto:{deployer_email}">{deployer_email}</a>.</p>
        </div>
    """

    st.markdown(footer, unsafe_allow_html=True)

    # container_placeholder = st.empty()

    # st.markdown('</div>', unsafe_allow_html=True)

    async def search_button_clicked():
        query_response = {}
        container_placeholder.empty()

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
                container_placeholder.empty()

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
        await search_button_clicked()


asyncio.run(app())
