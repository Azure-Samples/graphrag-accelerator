import streamlit as st
from enums import PromptKeys
from functions import set_session_state_variables

# def set_session_state_variables() -> None:
#     """
#     Initalizes most session state variables for the app.
#     """
#     for key in PromptKeys:
#         value = key.value
#         if value not in st.session_state:
#             st.session_state[value] = ""
#     for key in StorageIndexVars:
#         value = key.value
#         if value not in st.session_state:
#             st.session_state[value] = ""
#     if "saved_prompts" not in st.session_state:
#         st.session_state["saved_prompts"] = False


def save_prompts():
    """
    Save the prompts to the server
    """
    st.session_state["saved_prompts"] = True


def edit_prompts():
    """
    Re-edit the prompts
    """
    st.session_state["saved_prompts"] = False


def prompt_expander_():
    """
    Expander for prompt configurations
    """
    saved_prompts = st.session_state["saved_prompts"]
    entity_ext_prompt = st.session_state[PromptKeys.ENTITY.value]
    summ_prompt = st.session_state[PromptKeys.SUMMARY.value]
    comm_report_prompt = st.session_state[PromptKeys.COMMUNITY.value]

    with st.expander(
        label="Prompt Configurations",
        expanded=True,
    ):
        with st.container(border=True):
            tab_labels = [
                "Entity Extraction",
                "Summarize Descriptions",
                "Community Reports",
            ]
            subheaders = [f"{tab_label} Prompt" for tab_label in tab_labels]
            tab1, tab2, tab3 = st.tabs(tabs=tab_labels)
            with tab1:
                st.subheader(subheaders[0])
                entity_prompt = st.text_area(
                    label="Entity Prompt",
                    value=entity_ext_prompt,
                    max_chars=20000,
                    key="entity_text_area",
                    label_visibility="hidden",
                    disabled=saved_prompts,
                )
                st.session_state[PromptKeys.ENTITY.value] = (
                    st.session_state["entity_text_area"]
                    if entity_prompt
                    else entity_ext_prompt
                )
            with tab2:
                st.subheader(subheaders[1])
                summary_prompt = st.text_area(
                    label="Summarize Prompt",
                    value=summ_prompt,
                    max_chars=20000,
                    key="summarize_text_area",
                    label_visibility="hidden",
                    disabled=saved_prompts,
                )
                st.session_state[PromptKeys.SUMMARY.value] = (
                    summary_prompt if summary_prompt else summ_prompt
                )
            with tab3:
                st.subheader(subheaders[2])
                community_prompt = st.text_area(
                    label="Community Reports Prompt",
                    value=comm_report_prompt,
                    max_chars=20000,
                    key="community_text_area",
                    label_visibility="hidden",
                    disabled=saved_prompts,
                )
                st.session_state[PromptKeys.COMMUNITY.value] = (
                    community_prompt if community_prompt else comm_report_prompt
                )


if __name__ == "__main__":
    set_session_state_variables()
    prompt_expander_()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.button("Save Prompts", on_click=save_prompts)
    with col2:
        st.button("Re-edit Prompts", on_click=edit_prompts)
    with col3:
        st.download_button("Download Prompts", "prompts.txt", "Download")
    entity_ext_prompt = st.session_state[PromptKeys.ENTITY.value]
    summ_prompt = st.session_state[PromptKeys.SUMMARY.value]
    comm_report_prompt = st.session_state[PromptKeys.COMMUNITY.value]
    st.write(entity_ext_prompt)
    st.write(summ_prompt)
    st.write(comm_report_prompt)
