# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
from time import sleep

import streamlit as st

from src.components.index_pipeline import IndexPipeline
from src.components.login_sidebar import login
from src.components.prompt_configuration import (
    edit_prompts,
    prompt_editor,
    save_prompts,
)
from src.components.query import GraphQuery
from src.components.upload_files_component import upload_files
from src.enums import PromptKeys
from src.functions import generate_and_extract_prompts
from src.graphrag_api import GraphragAPI


def get_main_tab(initialized: bool) -> None:
    """
    Displays content of Main Tab
    """

    url = "https://github.com/Azure-Samples/graphrag-accelerator/blob/main/TRANSPARENCY.md"
    content = f"""
    ##  Welcome to GraphRAG!
    Diving into complex information and uncovering semantic relationships utilizing generative AI has never been easier.
    Here's how you can get started with just a few clicks:
    - **PROMPT GENERATION:** (*Optional Step*)
        1. Generate fine-tuned prompts for graphrag customized to your data and domain.
        2. Select an existing Storage Container and click "Generate Prompts".
    - **PROMPT CONFIGURATION:** (*Optional Step*)
        1. Edit the generated prompts to best suit your needs.
        2. Once you are finished editing, click the "Save Prompts" button.
        3. Saving the prompts will store them for use in the follow-on Indexing step.
        4. You can also download the edited prompts for future reference.
    - **INDEXING:**
        1. Select an existing data storage container or upload data, to Index
        2. Name your index and select "Build Index" to begin building a GraphRAG Index.
        3. Check the status of the index as the job progresses.
    - **QUERYING:**
        1. Choose an existing index
        2. Specify a query type
        3. Click "Query" button to search and view insights.

    [GraphRAG]({url}) combines the power of RAG with a Graph structure, giving you insights at your fingertips.
    """
    # Display text in the gray box
    st.markdown(content, unsafe_allow_html=False)
    if not initialized:
        login()


def get_prompt_generation_tab(
    client: GraphragAPI,
    column_widths: list[float],
    num_chunks: int = 5,
) -> None:
    """
    Displays content of Prompt Generation Tab
    """
    _, col2, _ = st.columns(column_widths)
    with col2:
        st.header(
            "Generate Prompts (optional)",
            divider=True,
            help="Generate fine-tuned prompts for graphrag tailored to your data and domain.",
        )

        st.write(
            "Select a storage container that contains your data. GraphRAG will use this data to generate domain-specific prompts for follow-on indexing."
        )
        storage_containers = client.get_storage_container_names()

        # if no storage containers, allow user to upload files
        if isinstance(storage_containers, list) and not (any(storage_containers)):
            st.warning(
                "No existing Storage Containers found. Please upload data to continue."
            )
            uploaded = upload_files(client, key_prefix="prompts-upload-1")
            if uploaded:
                # brief pause to allow success message to display
                sleep(1.5)
                st.rerun()
        else:
            select_prompt_storage = st.selectbox(
                "Select an existing Storage Container.",
                options=[""] + storage_containers
                if isinstance(storage_containers, list)
                else [],
                key="prompt-storage",
                index=0,
            )
            disable_other_input = True if select_prompt_storage != "" else False
            with st.expander("I want to upload new data...", expanded=False):
                new_upload = upload_files(
                    client,
                    key_prefix="prompts-upload-2",
                    disable_other_input=disable_other_input,
                )
                if new_upload:
                    # brief pause to allow success message to display
                    st.session_state["new_upload"] = True
                    sleep(1.5)
                    st.rerun()
            if st.session_state["new_upload"] and not select_prompt_storage:
                st.warning(
                    "Please select the newly uploaded Storage Container to continue."
                )
            st.write(f"**Selected Storage Container:** :blue[{select_prompt_storage}]")
            triggered = st.button(
                label="Generate Prompts",
                key="prompt-generation",
                help="Select either an existing Storage Container or upload new data to enable this button.\n\
                Then, click to generate custom prompts for the LLM.",
                disabled=not select_prompt_storage,
            )
            if triggered:
                with st.spinner("Generating LLM prompts for GraphRAG..."):
                    generated = generate_and_extract_prompts(
                        client=client,
                        storage_name=select_prompt_storage,
                        limit=num_chunks,
                    )
                    if not isinstance(generated, Exception):
                        st.success(
                            "Prompts generated successfully! Move on to the next tab to configure the prompts."
                        )
                    else:
                        # limit parameter was too high
                        st.warning(
                            "You do not have enough data to generate prompts. Retrying with a smaller sample size."
                        )


def get_prompt_configuration_tab(
    download_file_name: str = "edited_prompts.zip",
) -> None:
    """
    Displays content of Prompt Configuration Tab
    """
    st.header(
        "Configure Prompts (optional)",
        divider=True,
        help="Generate fine tuned prompts for the LLM specific to your data and domain.",
    )
    prompt_values = [st.session_state[k.value] for k in PromptKeys]

    if any(prompt_values):
        prompt_editor([prompt_values[0], prompt_values[1], prompt_values[2]])
        col1, col2, col3 = st.columns(3, gap="large")
        with col1:
            clicked = st.button(
                "Save Prompts",
                help="Save the edited prompts for use with the follow-on indexing step. This button must be clicked to enable downloading the prompts.",
                type="primary",
                key="save-prompt-button",
                on_click=save_prompts,
                kwargs={"zip_file_path": download_file_name},
            )
        with col2:
            st.button(
                "Edit Prompts",
                help="Allows user to re-edit the prompts after saving.",
                type="primary",
                key="edit-prompt-button",
                on_click=edit_prompts,
            )
        with col3:
            if os.path.exists(download_file_name):
                with open(download_file_name, "rb") as fp:
                    st.download_button(
                        "Download Prompts",
                        data=fp,
                        file_name=download_file_name,
                        help="Downloads the saved prompts as a zip file containing three LLM prompts in .txt format.",
                        mime="application/zip",
                        type="primary",
                        disabled=not st.session_state["saved_prompts"],
                        key="download-prompt-button",
                    )
        if clicked:
            st.success(
                "Prompts saved successfully! Downloading prompts is now enabled."
            )


def get_index_tab(indexPipe: IndexPipeline) -> None:
    """
    Displays content of Index tab
    """
    indexPipe.storage_data_step()
    indexPipe.build_index_step()
    indexPipe.check_status_step()


def execute_query(
    query_engine: GraphQuery, query_type: str, search_index: str | list[str], query: str
) -> None:
    """
    Executes the query on the selected index
    """
    if query:
        query_engine.search(
            query_type=query_type, search_index=search_index, query=query
        )
    else:
        return st.warning("Please enter a query to search.")


def get_query_tab(client: GraphragAPI) -> None:
    """
    Displays content of Query Tab
    """
    gquery = GraphQuery(client)
    col1, col2 = st.columns(2)
    with col1:
        query_type = st.selectbox(
            "Query Type",
            # ["Global Streaming", "Local Streaming", "Global", "Local"],
            ["Global", "Local"],
            help=(
                "Select the query type - Each yeilds different results of specificity. Global queries focus on the entire graph structure. Local queries focus on a set of communities (subgraphs) in the graph that are more connected to each other than they are to the rest of the graph structure and can focus on very specific entities in the graph."
            ),
        )
    with col2:
        search_indexes = client.get_index_names()
        if not any(search_indexes):
            st.warning("No indexes found. Please build an index to continue.")
        select_index_search = st.multiselect(
            label="Index",
            options=search_indexes if any(search_indexes) else [],
            key="multiselect-index-search",
            help="Select the index(es) to query. The selected index(es) must have a complete status in order to yield query results without error. Use Check Index Status to confirm status.",
        )

    disabled = True if not any(select_index_search) else False
    col3, col4 = st.columns([0.8, 0.2])
    with col3:
        search_bar = st.text_input("Query", key="search-query", disabled=disabled)
    with col4:
        search_button = st.button("QUERY", type="primary", disabled=disabled)

    # defining a query variable enables the use of either the search bar or the search button to trigger the query
    query = st.session_state["search-query"]
    if len(query) > 5:
        if (search_bar and search_button) and any(select_index_search):
            execute_query(
                query_engine=gquery,
                query_type=query_type,
                search_index=select_index_search,
                query=query,
            )
    else:
        col1, col2 = st.columns([0.3, 0.7])
        with col1:
            st.warning("Cannot submit queries less than 6 characters in length.")
