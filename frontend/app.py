# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import os

import streamlit as st
from src.app_utilities.enums import EnvVars

# from dotenv import load_dotenv
from src.app_utilities.functions import get_storage_container_names, initialize_app
from src.components import tabs
from src.components.index_pipeline import IndexPipeline

# Load environment variables
initialized = initialize_app()
st.session_state["initialized"] = True if initialized else False


def graphrag_app(initialized: bool):
    # main entry point
    st.title("Microsoft GraphRAG Copilot")
    main_tab, prompt_gen_tab, prompt_edit_tab, index_tab, query_tab = st.tabs(
        [
            "**Intro**",
            "**1. Prompt Generation**",
            "**2. Prompt Configuration**",
            "**3. Index**",
            "**4. Query**",
        ]
    )
    with main_tab:
        tabs.get_main_tab(initialized)
    if initialized:
        # assign API request information
        api_url = st.session_state[EnvVars.DEPLOYMENT_URL.value]
        headers = st.session_state["headers"]
        headers_upload = st.session_state["headers_upload"]
        # set constants
        containers = get_storage_container_names(api_url, headers)
        indexPipe = IndexPipeline(containers, api_url, headers, headers_upload)
        # display tabs
        with prompt_gen_tab:
            tabs.get_prompt_generation_tab(indexPipe)
        with prompt_edit_tab:
            tabs.get_prompt_configuration_tab()
        with index_tab:
            tabs.get_index_tab(containers, api_url, headers, headers_upload)
        with query_tab:
            tabs.get_query_tab(api_url, headers)

    deployer_email = os.getenv("DEPLOYER_EMAIL", "deployer@email.com")

    footer = f"""
        <div class="footer">
            <p> Responses may be inaccurate; please review all responses for accuracy. Learn more about Azure OpenAI code of conduct <a href="https://learn.microsoft.com/en-us/legal/cognitive-services/openai/code-of-conduct"> here</a>. </br> For feedback, email us at <a href="mailto:{deployer_email}">{deployer_email}</a>.</p>
        </div>
    """
    st.markdown(footer, unsafe_allow_html=True)


if __name__ == "__main__":
    graphrag_app(st.session_state["initialized"])
