# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
import os
from pathlib import Path
from typing import Optional
from zipfile import ZipFile

import streamlit as st

from src.enums import EnvVars, PromptKeys, StorageIndexVars
from src.graphrag_api import GraphragAPI

"""
This module contains functions that are used across the Streamlit app.
"""


def initialize_app(css_file: str = "style.css") -> bool:
    """
    Initialize the Streamlit app with the necessary configurations.
    """
    # set page configuration
    st.set_page_config(initial_sidebar_state="expanded", layout="wide")

    # set custom CSS
    with open(css_file) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    # initialize session state variables
    set_session_state_variables()

    # load settings from environment variables
    st.session_state[EnvVars.APIM_SUBSCRIPTION_KEY.value] = os.getenv(
        EnvVars.APIM_SUBSCRIPTION_KEY.value,
        st.session_state[EnvVars.APIM_SUBSCRIPTION_KEY.value],
    )
    st.session_state[EnvVars.DEPLOYMENT_URL.value] = os.getenv(
        EnvVars.DEPLOYMENT_URL.value, st.session_state[EnvVars.DEPLOYMENT_URL.value]
    )
    if (
        st.session_state[EnvVars.APIM_SUBSCRIPTION_KEY.value]
        and st.session_state[EnvVars.DEPLOYMENT_URL.value]
    ):
        st.session_state["headers"] = {
            "Ocp-Apim-Subscription-Key": st.session_state[
                EnvVars.APIM_SUBSCRIPTION_KEY.value
            ],
            "Content-Type": "application/json",
        }
        st.session_state["headers_upload"] = {
            "Ocp-Apim-Subscription-Key": st.session_state[
                EnvVars.APIM_SUBSCRIPTION_KEY.value
            ]
        }
        return True
    else:
        return False


def set_session_state_variables() -> None:
    """
    Initalizes most session state variables for the app.
    """
    for key in PromptKeys:
        value = key.value
        if value not in st.session_state:
            st.session_state[value] = ""
    for key in StorageIndexVars:
        value = key.value
        if value not in st.session_state:
            st.session_state[value] = ""
    for key in EnvVars:
        value = key.value
        if value not in st.session_state:
            st.session_state[value] = ""
    if "saved_prompts" not in st.session_state:
        st.session_state["saved_prompts"] = False
    if "initialized" not in st.session_state:
        st.session_state["initialized"] = False
    if "new_upload" not in st.session_state:
        st.session_state["new_upload"] = False


def update_session_state_prompt_vars(
    entity_extract: Optional[str] = None,
    summarize: Optional[str] = None,
    community: Optional[str] = None,
    initial_setting: bool = False,
    prompt_dir: str = "./prompts",
) -> None:
    """
    Updates the session state variables for the LLM prompts.
    """
    if initial_setting:
        entity_extract, summarize, community = get_prompts(prompt_dir)
    if entity_extract:
        st.session_state[PromptKeys.ENTITY.value] = entity_extract
    if summarize:
        st.session_state[PromptKeys.SUMMARY.value] = summarize
    if community:
        st.session_state[PromptKeys.COMMUNITY.value] = community


def generate_and_extract_prompts(
    client: GraphragAPI,
    storage_name: str,
    zip_file_name: str = "prompts.zip",
    limit: int = 5,
) -> None | Exception:
    """
    Makes API call to generate LLM prompts, extracts prompts from zip file,
    and updates the prompt session state variables.
    """
    try:
        client.generate_prompts(
            storage_name=storage_name, zip_file_name=zip_file_name, limit=limit
        )
        _extract_prompts_from_json(zip_file_name)
        update_session_state_prompt_vars(initial_setting=True, prompt_dir=".")
        return
    except Exception as e:
        return e


def _extract_prompts_from_json(json_file_name: str = "prompts.zip"):
    with open(json_file_name, "r", encoding="utf-8") as file:
        json_data = file.read()

    json_data = json.loads(json_data)

    with open("entity_extraction_prompt.txt", "w", encoding="utf-8") as file:
        file.write(json_data["entity_extraction_prompt"])

    with open("summarization_prompt.txt", "w", encoding="utf-8") as file:
        file.write(json_data["entity_summarization_prompt"])

    with open("community_summarization_prompt.txt", "w", encoding="utf-8") as file:
        file.write(json_data["community_summarization_prompt"])

    return json_data


def _extract_prompts_from_zip(zip_file_name: str = "prompts.zip"):
    with ZipFile(zip_file_name, "r") as zip_ref:
        zip_ref.extractall()


def open_file(file_path: str | Path):
    with open(file_path, "r", encoding="utf-8") as file:
        text = file.read()
    return text


def zip_directory(directory_path: str, zip_path: str):
    """
    Zips all contents of a directory into a single zip file.

    Parameters:
    - directory_path: str, the path of the directory to zip
    - zip_path: str, the path where the zip file will be created
    """
    root_dir_name = os.path.basename(directory_path.rstrip("/"))
    with ZipFile(zip_path, "w") as zipf:
        for root, _, files in os.walk(directory_path):
            for file in files:
                file_path = os.path.join(root, file)
                relpath = os.path.relpath(file_path, start=directory_path)
                arcname = os.path.join(root_dir_name, relpath)
                zipf.write(file_path, arcname)


def get_prompts(prompt_dir: str = "./prompts"):
    """
    Extract text from generated prompts.  Assumes file names comply with pregenerated file name standards.
    """
    prompt_paths = [
        prompt for prompt in Path(prompt_dir).iterdir() if prompt.name.endswith(".txt")
    ]
    entity_ext_prompt = [
        open_file(path) for path in prompt_paths if path.name.startswith("entity")
    ][0]
    summ_prompt = [
        open_file(path) for path in prompt_paths if path.name.startswith("summ")
    ][0]
    comm_report_prompt = [
        open_file(path) for path in prompt_paths if path.name.startswith("community")
    ][0]
    return entity_ext_prompt, summ_prompt, comm_report_prompt
