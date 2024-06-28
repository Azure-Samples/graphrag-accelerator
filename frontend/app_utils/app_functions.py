import requests
import streamlit as st


# Function to call the REST API and return storage data
@st.cache_data
def get_storage_data(api_url: str, headers: dict) -> dict | None:
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
@st.cache_data
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
@st.cache_data
def get_indexes_data(api_url: str, headers: dict) -> dict | None:
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


async def query_index(
    index_name: list[str], query_type: str, query: str, api_url: str, headers: dict
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
            st.error(f"Error: {response.status_code} {response.json()}")
            return None
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None


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
            st.error(f"Error: {response.status_code} {response.json()}")
            return None
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None


def show_index_options(indexes: dict) -> list[str]:
    options_indexes = [""]
    try:
        options_indexes = options_indexes + indexes["index_name"]
    except Exception as e:
        print(f"No indexes found, continuing...\nException: {str(e)}")
    return options_indexes
