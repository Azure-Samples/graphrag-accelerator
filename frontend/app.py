# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os

import streamlit as st
from src.components import tabs
from src.components.index_pipeline import IndexPipeline
from src.enums import EnvVars
from src.functions import initialize_app
from src.graphrag_api import GraphragAPI
import base64


# Load environment variables
initialized = initialize_app()
st.session_state["initialized"] = True if initialized else False


# def get_base64(bin_file):
#     with open(bin_file, 'rb') as f:
#         data = f.read()
#     return base64.b64encode(data).decode()

# def set_background(png_file):
#     bin_str = get_base64(png_file)
#     page_bg_img = '''
#     <style>
#     .stApp {
#     background-image: url("data:image/png;base64,%s");
#     background-size: cover;
#     }
#     </style>
#     ''' % bin_str
#     st.markdown(page_bg_img, unsafe_allow_html=True)


def graphrag_app(initialized: bool):
    # main entry point for app interface
    # st.title("Microsoft GraphRAG Copilot")
    st.markdown(
    f"""
    <div class="header-container">
        <img src="https://upload.wikimedia.org/wikipedia/commons/2/2a/Microsoft_365_Copilot_Icon.svg" alt="Logo">
        <h1>Microsoft GraphRAG Copilot</h1>
    </div>
    """,
    unsafe_allow_html=True
)
    # set_background('./src/images/background3.png')

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

    # if not initialized, only main tab is displayed
    if initialized:
        # assign API request information
        COLUMN_WIDTHS = [0.275, 0.45, 0.275]
        api_url = st.session_state[EnvVars.DEPLOYMENT_URL.value]
        apim_key = st.session_state[EnvVars.APIM_SUBSCRIPTION_KEY.value]
        client = GraphragAPI(api_url, apim_key)
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
