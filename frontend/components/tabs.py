import streamlit as st

from .functions import show_index_options
from .index_pipeline import IndexPipeline
from .query import GraphQuery


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
    containers: dict, api_url: str, headers: dict, headers_upload: dict
) -> None:
    """
    Displays content of Index tab
    """
    pipeline = IndexPipeline(containers, api_url, headers, headers_upload)
    pipeline.storage_data_step()
    pipeline.prompt_config_step()
    pipeline.build_index_step()
    pipeline.check_status_step()


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


def get_query_tab(api_url: str, headers: dict) -> None:
    """
    Displays content of Query Tab
    """
    gquery = GraphQuery(api_url, headers)
    col1, col2 = st.columns(2)
    with col1:
        query_type = st.selectbox(
            "Query Type",
            ["Global Streaming", "Global", "Local"],
            help="Select the query type - Each yeilds different results of specificity. Global queries focus on the entire graph structure. Local queries focus on a set of communities (subgraphs) in the graph that are more connected to each other than they are to the rest of the graph structure and can focus on very specific entities in the graph. Global streaming is a global query that displays results as they appear live.",
        )
    with col2:
        select_index_search = st.selectbox(
            label="Index",
            options=show_index_options(api_url, headers),
            index=1,
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
