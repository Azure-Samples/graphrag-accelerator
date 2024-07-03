import os
from io import StringIO
from pathlib import Path
from typing import Optional
from zipfile import ZipFile

import requests
import streamlit as st
from dotenv import find_dotenv, load_dotenv
from src.app_utilities.enums import EnvVars, PromptKeys, StorageIndexVars


def initialize_app(
    env_file: str = ".env", css_file: str = "style.css"
) -> tuple[str, str, str] | bool:
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

    # load environment variables
    _ = load_dotenv(find_dotenv(filename=env_file), override=True)

    # set key and deployment url variables
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


def apim_health_check(endpoint: str, key: str) -> int:
    """
    Check the health of the APIM endpoint.
    """
    url = endpoint + "/health"
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/json",
    }
    try:
        response = requests.get(url, headers=headers)
        return response.status_code
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return 500


# Function to call the REST API and return storage data
def get_storage_container_names(api_url: str, headers: dict) -> dict | None:
    """
    GET request to GraphRAG API for Azure Blob Storage Container names.
    """
    try:
        response = requests.get(f"{api_url}/data", headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None


# Function to call the REST API and return existing entity config
def get_entity_data(api_url: str, headers: dict) -> dict | None:
    try:
        response = requests.get(f"{api_url}/index/config/entity", headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None


# Function to call the REST API and return existing entity config
def get_indexes_data(api_url: str, headers: dict) -> dict | None:
    """
    GET request to GraphRAG API for existing indexes.
    """
    try:
        response = requests.get(f"{api_url}/index", headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None


def build_index(
    api_url: str,
    headers: dict,
    storage_name: str,
    index_name: str,
    entity_extraction_prompt_filepath: str | StringIO = None,
    community_prompt_filepath: str | StringIO = None,
    summarize_description_prompt_filepath: str | StringIO = None,
) -> requests.Response:
    """Create a search index.
    This function kicks off a job that builds a knowledge graph (KG) index from files located in a blob storage container.
    """
    url = api_url + "/index"
    prompt_files = dict()
    if entity_extraction_prompt_filepath:
        prompt_files["entity_extraction_prompt"] = (
            open(entity_extraction_prompt_filepath, "r")
            if isinstance(entity_extraction_prompt_filepath, str)
            else entity_extraction_prompt_filepath
        )
    if community_prompt_filepath:
        prompt_files["community_report_prompt"] = (
            open(community_prompt_filepath, "r")
            if isinstance(community_prompt_filepath, str)
            else community_prompt_filepath
        )
    if summarize_description_prompt_filepath:
        prompt_files["summarize_descriptions_prompt"] = (
            open(summarize_description_prompt_filepath, "r")
            if isinstance(summarize_description_prompt_filepath, str)
            else summarize_description_prompt_filepath
        )
    return requests.post(
        url,
        files=prompt_files if len(prompt_files) > 0 else None,
        params={"index_name": index_name, "storage_name": storage_name},
        headers=headers,
    )


def query_index(
    index_name: str, query_type: str, query: str, api_url: str, headers: dict
):
    try:
        request = {
            "index_name": index_name,
            "query": query,
            "reformat_context_data": True,
        }
        response = requests.post(
            f"{api_url}/query/{query_type.lower()}", headers=headers, json=request
        )

        if response.status_code == 200:
            return response.json()
        else:
            st.error(
                f"Error with {query_type} search: {response.status_code} {response.json()}"
            )
    except Exception as e:
        st.error(f"Error with {query_type} search: {str(e)}")


def global_streaming_query(index_name: str, query: str, api_url: str, headers: dict):
    url = f"{api_url}/experimental/query/global/streaming"
    try:
        query_response = requests.post(
            url,
            json={"index_name": index_name, "query": query},
            headers=headers,
            stream=True,
        )
        return query_response
    except Exception as e:
        st.error(f"Error: {str(e)}")


def get_source_entity(
    index_name: str, entity_id: str, api_url: str, headers: dict
) -> dict | None:
    try:
        response = requests.get(
            f"{api_url}/source/entity/{index_name}/{entity_id}", headers=headers
        )
        if response.status_code == 200:
            return response.json()
        else:
            return response.json()
        # else:
        #     st.error(f"Error: {response.status_code} {response.json()}")
    except Exception as e:
        st.error(f"Error: {str(e)}")


def show_index_options(api_url: str, headers: dict) -> list[str]:
    """
    Makes a GET request to the GraphRAG API to get the existing indexes
    and returns a list of index names.
    """
    indexes = get_indexes_data(api_url, headers)
    try:
        options_indexes = indexes["index_name"]
        return options_indexes
    except Exception as e:
        print(f"No indexes found, continuing...\nException: {str(e)}")


def _generate_prompts(
    api_url: str,
    headers: dict,
    storage_name: str,
    zip_file_name: str = "prompts.zip",
    limit: int = 5,
) -> None:
    """
    Generate graphrag prompts using data provided in a specific storage container.
    """
    url = api_url + "/index/config/prompts"
    params = {"storage_name": storage_name, "limit": limit}
    with requests.get(url, params=params, headers=headers, stream=True) as r:
        r.raise_for_status()
        with open(zip_file_name, "wb") as f:
            for chunk in r.iter_content():
                f.write(chunk)


def _extract_prompts_from_zip(zip_file_name: str = "prompts.zip"):
    with ZipFile(zip_file_name, "r") as zip_ref:
        zip_ref.extractall()


def generate_and_extract_prompts(
    api_url: str,
    headers: str,
    storage_name: str,
    zip_file_name: str = "prompts.zip",
    limit: int = 5,
) -> None:
    _generate_prompts(api_url, headers, storage_name, zip_file_name, limit)
    _extract_prompts_from_zip(zip_file_name)
    update_session_state_prompt_vars(initial_setting=True)


def open_file(file_path: str | Path):
    with open(file_path, "r") as file:
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
