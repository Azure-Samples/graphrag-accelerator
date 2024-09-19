# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os

import streamlit as st

from src.components import tabs
from src.components.index_pipeline import IndexPipeline
from src.enums import EnvVars
from src.functions import initialize_app
from src.graphrag_api import GraphragAPI

# Load environment variables
initialized = initialize_app()
st.session_state["initialized"] = True if initialized else False


def graphrag_app(initialized: bool):
    st.title("Microsoft GraphRAG Copilot")
    main_tab, prompt_gen_tab, prompt_edit_tab, index_tab, query_tab = st.tabs([
        "**Intro**",
        "**1. Prompt Generation**",
        "**2. Prompt Configuration**",
        "**3. Index**",
        "**4. Query**",
    ])
    # display only the main tab if a connection to an existing APIM has not been initialized
    with main_tab:
        tabs.get_main_tab(initialized)
    if initialized:
        # setup API request information
        COLUMN_WIDTHS = [0.275, 0.45, 0.275]
        apim_url = st.session_state[EnvVars.DEPLOYMENT_URL.value]
        apim_key = st.session_state[EnvVars.APIM_SUBSCRIPTION_KEY.value]
        # perform health check to verify connectivity
        client = GraphragAPI(apim_url, apim_key)
        if not client.health_check_passed():
            st.error("APIM Connection Error")
            st.stop()
        indexPipe = IndexPipeline(client, COLUMN_WIDTHS)
        # display tabs
        with prompt_gen_tab:
            tabs.get_prompt_generation_tab(client, COLUMN_WIDTHS)
        with prompt_edit_tab:
            tabs.get_prompt_configuration_tab()
        with index_tab:
            tabs.get_index_tab(indexPipe)
        with query_tab:
            tabs.get_query_tab(client)
    deployer_email = os.getenv("DEPLOYER_EMAIL", "deployer@email.com")
    footer = f"""
        <div class="footer">
            <p> Responses may be inaccurate; please review all responses for accuracy. Learn more about Azure OpenAI code of conduct <a href="https://learn.microsoft.com/en-us/legal/cognitive-services/openai/code-of-conduct"> here</a>. </br> For feedback, email us at <a href="mailto:{deployer_email}">{deployer_email}</a>.</p>
        </div>
    """
    st.markdown(footer, unsafe_allow_html=True)


if __name__ == "__main__":
    graphrag_app(st.session_state["initialized"])
