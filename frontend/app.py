# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import os

import streamlit as st
from components import tabs
from components.functions import (
    get_indexes_data,
    get_storage_container_names,
    set_session_state_variables,
)
from dotenv import load_dotenv

_ = load_dotenv(override=True)

### SET CONSTANTS AND VARIABLES ###
st.set_page_config(initial_sidebar_state="expanded", layout="wide")
set_session_state_variables()
with open("style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

headers = {
    "Ocp-Apim-Subscription-Key": os.environ["APIM_SUBSCRIPTION_KEY"],
    "Content-Type": "application/json",  # Include other headers as needed
}
headers_upload = {"Ocp-Apim-Subscription-Key": os.environ["APIM_SUBSCRIPTION_KEY"]}

# API endpoint URL
api_url = os.environ["DEPLOYMENT_URL"]
indexes = get_indexes_data(api_url, headers)
containers = get_storage_container_names(api_url, headers)
input_storage_name = ""
select_storage_name = ""


def graphrag_app():
    # main entry point
    st.title("Microsoft GraphRAG Copliot")
    main_tab, index_tab, query_tab = st.tabs(["**Main**", "**Index**", "**Query**"])
    with main_tab:
        tabs.get_main_tab()
    with index_tab:
        tabs.get_index_tab(containers, api_url, headers, headers_upload)
    with query_tab:
        tabs.get_query_tab(api_url, headers)

    deployer_email = os.environ.get("DEPLOYER_EMAIL", "deployer@email.com")
    footer = f"""
        <div class="footer">
            <p> Responses may be inaccurate; please review all responses for accuracy. Learn more about Azure OpenAI code of conduct <a href="https://learn.microsoft.com/en-us/legal/cognitive-services/openai/code-of-conduct"> here</a>. </br> For feedback, email us at <a href="mailto:{deployer_email}">{deployer_email}</a>.</p>
        </div>
    """
    st.markdown(footer, unsafe_allow_html=True)


if __name__ == "__main__":
    graphrag_app()
