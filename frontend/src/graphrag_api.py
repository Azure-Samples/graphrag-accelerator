# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from io import StringIO

import requests
import streamlit as st
from requests import Response

"""
This module contains the GraphRAG API class for making all external API calls
presumably to a GraphRAG instance deployed on Azure.
"""


class GraphragAPI:
    """
    Primary interface for making REST API call to GraphRAG API.
    """

    def __init__(self, api_url: str, apim_key: str):
        self.api_url = api_url
        self.apim_key = apim_key
        self.headers = {
            "Ocp-Apim-Subscription-Key": self.apim_key,
            "Content-Type": "application/json",
        }
        self.upload_headers = {"Ocp-Apim-Subscription-Key": self.apim_key}

    def get_storage_container_names(
        self, storage_name_key: str = "storage_name"
    ) -> list[str] | Response | Exception:
        """
        GET request to GraphRAG API for Azure Blob Storage Container names.
        """
        try:
            response = requests.get(f"{self.api_url}/data", headers=self.headers)
            if response.status_code == 200:
                return response.json()[storage_name_key]
            else:
                print(f"Error: {response.status_code}")
                return response
        except Exception as e:
            print(f"Error: {str(e)}")
            return e

    def upload_files(
        self, file_payloads: dict, container_name: str, overwrite: bool = True
    ):
        """
        Upload files to Azure Blob Storage Container.
        """
        try:
            response = requests.post(
                self.api_url + "/data",
                headers=self.upload_headers,
                files=file_payloads,
                params={"container_name": container_name, "overwrite": overwrite},
            )
            if response.status_code == 200:
                return response
        except Exception as e:
            print(f"Error: {str(e)}")

    def get_index_names(
        self, index_name_key: str = "index_name"
    ) -> list | Response | None:
        """
        GET request to GraphRAG API for existing indexes.
        """
        try:
            response = requests.get(f"{self.api_url}/index", headers=self.headers)
            if response.status_code == 200:
                return response.json()[index_name_key]
            else:
                print(f"Error: {response.status_code}")
                return response
        except Exception as e:
            print(f"Error: {str(e)}")

    def build_index(
        self,
        storage_container_name: str,
        index_container_name: str,
        entity_extraction_prompt_filepath: str | StringIO = None,
        community_prompt_filepath: str | StringIO = None,
        summarize_description_prompt_filepath: str | StringIO = None,
    ) -> requests.Response:
        """
        Create a search index.
        This function kicks off a job that builds a knowledge graph (KG)
        index from files located in a blob storage container.
        """
        url = self.api_url + "/index"
        prompt_files = dict()
        if entity_extraction_prompt_filepath:
            prompt_files["entity_extraction_prompt"] = (
                open(entity_extraction_prompt_filepath, "r", encoding="utf-8")
                if isinstance(entity_extraction_prompt_filepath, str)
                else entity_extraction_prompt_filepath
            )
        if community_prompt_filepath:
            prompt_files["community_report_prompt"] = (
                open(community_prompt_filepath, "r", encoding="utf-8")
                if isinstance(community_prompt_filepath, str)
                else community_prompt_filepath
            )
        if summarize_description_prompt_filepath:
            prompt_files["summarize_descriptions_prompt"] = (
                open(summarize_description_prompt_filepath, "r", encoding="utf-8")
                if isinstance(summarize_description_prompt_filepath, str)
                else summarize_description_prompt_filepath
            )
        return requests.post(
            url,
            files=prompt_files if len(prompt_files) > 0 else None,
            params={
                "storage_container_name": storage_container_name,
                "index_container_name": index_container_name,
            },
            headers=self.headers,
        )

    def check_index_status(self, index_name: str) -> Response | None:
        """
        Check the status of a running index job.
        """
        url = self.api_url + f"/index/status/{index_name}"
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                return response
            else:
                print(f"Error: {response.status_code}")
                return response
        except Exception as e:
            print(f"Error: {str(e)}")

    def health_check_passed(self) -> bool:
        """
        Check the health of the APIM endpoint.
        """
        url = self.api_url + "/health"
        try:
            response = requests.get(url, headers=self.headers)
            return response.ok
        except Exception:
            return False

    def query_index(self, index_name: str | list[str], query_type: str, query: str):
        """
        Submite query to GraphRAG API using specific index and query type.
        """

        if isinstance(index_name, list) and len(index_name) > 1:
            st.error(
                "Multiple index names are currently not supported via the UI. This functionality is being moved into the graphrag library and will be available in a coming release."
            )
            return {"result": ""}

        index_name = index_name if isinstance(index_name, str) else index_name[0]

        try:
            request = {
                "index_name": index_name,
                "query": query,
                # "reformat_context_data": True,
            }
            response = requests.post(
                f"{self.api_url}/query/{query_type.lower()}",
                headers=self.headers,
                json=request,
            )

            if response.status_code == 200:
                return response.json()
            else:
                st.error(
                    f"Error with {query_type} search: {response.status_code} {response.json()}"
                )
        except Exception as e:
            st.error(f"Error with {query_type} search: {str(e)}")

    def global_streaming_query(
        self, index_name: str | list[str], query: str
    ) -> Response | None:
        """
        Returns a streaming response object for a global query.
        """
        url = f"{self.api_url}/query/streaming/global"
        try:
            query_response = requests.post(
                url,
                json={"index_name": index_name, "query": query},
                headers=self.headers,
                stream=True,
            )
            return query_response
        except Exception as e:
            print(f"Error: {str(e)}")

    def local_streaming_query(
        self, index_name: str | list[str], query: str
    ) -> Response | None:
        """
        Returns a streaming response object for a global query.
        """
        url = f"{self.api_url}/query/streaming/local"
        try:
            query_response = requests.post(
                url,
                json={"index_name": index_name, "query": query},
                headers=self.headers,
                stream=True,
            )
            return query_response
        except Exception as e:
            print(f"Error: {str(e)}")

    def get_source_entity(self, index_name: str, entity_id: str) -> dict | None:
        try:
            response = requests.get(
                f"{self.api_url}/source/entity/{index_name}/{entity_id}",
                headers=self.headers,
            )
            if response.status_code == 200:
                return response.json()
            else:
                return response
        except Exception as e:
            print(f"Error: {str(e)}")

    def generate_prompts(
        self, storage_name: str, zip_file_name: str = "prompts.zip", limit: int = 1
    ) -> None:
        """
        Generate graphrag prompts using data provided in a specific storage container.
        """
        url = self.api_url + "/index/config/prompts"
        params = {"container_name": storage_name, "limit": limit}
        with requests.get(url, params=params, headers=self.headers, stream=True) as r:
            r.raise_for_status()
            with open(zip_file_name, "wb") as f:
                for chunk in r.iter_content():
                    f.write(chunk)
