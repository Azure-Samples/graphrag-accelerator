import os
from time import sleep

import streamlit as st

from src.app_utilities.enums import PromptKeys
from src.app_utilities.functions import GraphragAPI, generate_and_extract_prompts
from src.components.index_pipeline import IndexPipeline
from src.components.login_sidebar import login
from src.components.prompt_configuration import (
    edit_prompts,
    prompt_editor,
    save_prompts,
)
from src.components.query import GraphQuery
from src.components.upload_files_component import upload_files


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
        1. Generate fine-tuned prompts for the LLM specific to your data and domain.
        2. Simply select an existing Storage Container and click "Generate Prompts".
    - **PROMPT CONFIGURATION:** (*Optional Step*)
        1. Edit the generated prompts to better suit your needs.
        2. Once you are finished editing, click the "Save Prompts" button.
        3. Saving the prompts will store the prompts for use with the follow-on Indexing step.
        4. You can also download the edited prompts for future reference.
    - **INDEXING:**
        1. Select or upload your data to Index
        2. Name your index and click "Build Index" to begin building a GraphRAG Index.
        3. Check the status of the index as the job progresses.
    - **QUERYING:**
        1. Choose an existing index
        2. Specify the query type
        3. Hit "Enter" or click "Search" to view insights.

    [GraphRAG]({url}) combines the power of RAG with a Graph structure, giving you insights at your fingertips.
    """
    # Display text in the gray box
    st.markdown(content, unsafe_allow_html=False)
    if not initialized:
        login()


def get_prompt_generation_tab(client: GraphragAPI, num_files: int = 5) -> None:
    """
    Displays content of Prompt Generation Tab
    """
    # hard set limit to 5 files to reduce overly long processing times and to reduce over sample errors.
    num_files = num_files if num_files <= 5 else 5

    st.header(
        "1. LLM Prompt Generation (Optional)",
        divider=True,
        help="Generate fine tuned prompts for the LLM specific to your data and domain.",
    )

    st.write(
        "**OPTIONAL STEP:** Select a storage container that contains your data. The LLM will use that data to generate domain-specific prompts for follow-on indexing."
    )
    storage_containers = client.get_storage_container_names()

    # if no storage containers, allow user to upload files
    if not (any(storage_containers)):
        COLUMN_WIDTHS = [0.275, 0.45, 0.275]
        _, col2, _ = st.columns(COLUMN_WIDTHS)
        with col2:
            st.warning(
                "No existing Storage Containers found. Please upload data to continue."
            )
            uploaded = upload_files(client, key_prefix="prompts")
            if uploaded:
                # brief pause to allow success message to display
                sleep(1.5)
                st.rerun()
    else:
        select_prompt_storage = st.selectbox(
            "Select an existing Storage Container.",
            options=storage_containers if any(storage_containers) else [],
            key="prompt-storage",
            index=0,
        )
        st.write(f"**Selected Storage Container:** {select_prompt_storage}")
        triggered = st.button(
            label="Generate Prompts",
            key="prompt-generation",
            disabled=not any(storage_containers),
        )
        if triggered:
            with st.spinner("Generating LLM prompts for GraphRAG..."):
                generated = generate_and_extract_prompts(
                    client=client,
                    storage_name=select_prompt_storage,
                    limit=num_files,
                )
                if not isinstance(generated, Exception):
                    st.success(
                        "Prompts generated successfully! Move on to the next tab to configure the prompts."
                    )
                else:
                    # assume limit parametes is too high
                    st.warning(
                        "You do not have enough data to generate prompts. Retrying with a smaller sample size."
                    )
                    while num_files > 1:
                        num_files -= 1
                        generated = generate_and_extract_prompts(
                            client=client,
                            storage_name=select_prompt_storage,
                            limit=num_files,
                        )
                        if not isinstance(generated, Exception):
                            st.success(
                                "Prompts generated successfully! Move on to the next tab to configure the prompts."
                            )
                            break
                        else:
                            st.warning(f"Retrying with sample size: {num_files}")


def get_prompt_configuration_tab() -> None:
    """
    Displays content of Prompt Configuration Tab
    """
    st.header(
        "2. Configure Prompts (Optional)",
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
                type="primary",
                key="save-prompt-button",
                on_click=save_prompts,
            )
        with col2:
            st.button(
                "Edit Prompts",
                type="primary",
                key="edit-prompt-button",
                on_click=edit_prompts,
            )
        with col3:
            download_file = "edited_prompts.zip"
            if os.path.exists(download_file):
                with open(download_file, "rb") as fp:
                    st.download_button(
                        "Download Prompts",
                        data=fp,
                        file_name=download_file,
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
    query_engine: GraphQuery, query_type: str, search_index: str, query: str
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
            ["Global Streaming", "Global", "Local"],
            help="Select the query type - Each yeilds different results of specificity. Global queries focus on the entire graph structure. Local queries focus on a set of communities (subgraphs) in the graph that are more connected to each other than they are to the rest of the graph structure and can focus on very specific entities in the graph. Global streaming is a global query that displays results as they appear live.",
        )
    with col2:
        search_indexes = client.get_index_names()
        if not any(search_indexes):
            st.warning("No indexes found. Please build an index to continue.")
        select_index_search = st.selectbox(
            label="Index",
            options=search_indexes if any(search_indexes) else [],
            index=0,
            help="Select the index(es) to query. The selected index(es) must have a complete status in order to yield query results without error. Use Check Index Status to confirm status.",
        )
    col3, col4 = st.columns([0.8, 0.2])
    with col3:
        search_bar = st.text_input("Query", key="search-query")
    with col4:
        search_button = st.button("QUERY", type="primary")
    query = st.session_state["search-query"]

    if search_bar and not search_button:
        execute_query(
            query_engine=gquery,
            query_type=query_type,
            search_index=select_index_search,
            query=query,
        )
    if search_button:
        execute_query(
            query_engine=gquery,
            query_type=query_type,
            search_index=select_index_search,
            query=query,
        )
