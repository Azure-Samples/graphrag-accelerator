# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import streamlit as st

from src.enums import EnvVars
from src.graphrag_api import GraphragAPI


def login():
    """
    Login component that displays in the sidebar.  Requires the user to enter
    the APIM Gateway URL and Subscription Key to login.  After entering user
    credentials, a simple health check call is made to the GraphRAG API.
    """
    with st.sidebar:
        st.title(
            "Login",
            help="Enter your APIM credentials to get started.  Refreshing the browser will require you to login again.",
        )
        with st.form(key="login-form", clear_on_submit=True):
            apim_url = st.text_input("APIM Gateway URL", key="apim-url")
            apim_sub_key = st.text_input(
                "APIM Subscription Key", key="subscription-key"
            )
            form_submit = st.form_submit_button("Login")
            if form_submit:
                client = GraphragAPI(apim_url, apim_sub_key)
                if client.health_check_passed():
                    st.success("Login Successful")
                    st.session_state[EnvVars.DEPLOYMENT_URL.value] = apim_url
                    st.session_state[EnvVars.APIM_SUBSCRIPTION_KEY.value] = apim_sub_key
                    st.session_state["initialized"] = True
                    st.rerun()
                else:
                    st.error("Login Failed")
                    st.error("Please check the APIM Gateway URL and Subscription Key")
