import streamlit as st
from src.app_utilities.enums import EnvVars
from src.app_utilities.functions import apim_health_check


def login():
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
                status_code = apim_health_check(apim_url, apim_sub_key)
                if status_code == 200:
                    st.success("Login Successful")
                    st.session_state[EnvVars.DEPLOYMENT_URL.value] = apim_url
                    st.session_state[EnvVars.APIM_SUBSCRIPTION_KEY.value] = apim_sub_key
                    st.session_state["initialized"] = True
                    st.rerun()
                else:
                    st.error("Login Failed")
                    st.error("Please check the APIM Gateway URL and Subscription Key")
