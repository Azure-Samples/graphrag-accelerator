# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os

import streamlit as st

from src.enums import PromptFileNames, PromptKeys, PromptTextAreas
from src.functions import zip_directory

SAVED_PROMPT_VAR = "saved_prompts"


def save_prompts(
    local_dir: str = "./edited_prompts/", zip_file_path: str = "edited_prompts.zip"
):
    """
    Save prompts in memory and on disk as a zip file
    """
    st.session_state[SAVED_PROMPT_VAR] = True
    st.session_state[PromptKeys.ENTITY.value] = st.session_state[
        PromptTextAreas.ENTITY.value
    ]
    st.session_state[PromptKeys.SUMMARY.value] = st.session_state[
        PromptTextAreas.SUMMARY.value
    ]
    st.session_state[PromptKeys.COMMUNITY.value] = st.session_state[
        PromptTextAreas.COMMUNITY.value
    ]
    os.makedirs(local_dir, exist_ok=True)
    for key, filename in zip(PromptKeys, PromptFileNames):
        outpath = os.path.join(local_dir, filename.value)
        with open(outpath, "w", encoding="utf-8") as f:
            f.write(st.session_state[key.value])
    zip_directory(local_dir, zip_file_path)


def edit_prompts():
    """
    Re-edit the prompts
    """
    st.session_state[SAVED_PROMPT_VAR] = False


def prompt_editor(prompt_values: list[str]):
    """
    Container for prompt configurations
    """
    saved_prompts = st.session_state[SAVED_PROMPT_VAR]

    entity_ext_prompt, summ_prompt, comm_report_prompt = prompt_values

    with st.container(border=True):
        tab_labels = [
            "**Entity Extraction**",
            "**Summarize Descriptions**",
            "**Community Reports**",
        ]
        # subheaders = [f"{tab_label} Prompt" for tab_label in tab_labels]
        tab1, tab2, tab3 = st.tabs(tabs=tab_labels)
        with tab1:
            st.text_area(
                label="Entity Prompt",
                value=entity_ext_prompt,
                max_chars=20000,
                key="entity_text_area",
                label_visibility="hidden",
                disabled=saved_prompts,
            )

        with tab2:
            st.text_area(
                label="Summarize Prompt",
                value=summ_prompt,
                max_chars=20000,
                key="summary_text_area",
                label_visibility="hidden",
                disabled=saved_prompts,
            )

        with tab3:
            st.text_area(
                label="Community Reports Prompt",
                value=comm_report_prompt,
                max_chars=20000,
                key="community_text_area",
                label_visibility="hidden",
                disabled=saved_prompts,
            )
