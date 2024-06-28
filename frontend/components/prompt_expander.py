import streamlit as st

from .prompt_enum import PromptKeys

css = """
<style>
    .element-container:has(>.stTextArea), .stTextArea {
        display: block;
        margin-left: auto;
        margin-right: auto;
    }
    .stTextArea textarea {
        height: 500px;
    }
</style>
"""


def prompt_expander_():
    st.markdown(body=css, unsafe_allow_html=True)
    entity_ext_prompt = st.session_state[PromptKeys.ENTITY.value]
    summ_prompt = st.session_state[PromptKeys.SUMMARY.value]
    comm_report_prompt = st.session_state[PromptKeys.COMMUNITY.value]

    with st.expander(label="Prompt Configurations", expanded=True):
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
                )
                st.session_state[PromptKeys.COMMUNITY.value] = (
                    community_prompt if community_prompt else comm_report_prompt
                )
        for i, k in enumerate(st.session_state):
            print(f"KEY {i}: {k}")
            print(f"VALUE: {st.session_state[k]}")
