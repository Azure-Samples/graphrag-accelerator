import json

import requests
import streamlit as st
from components.enums import PromptKeys, StorageIndexVars
from components.functions import (
    build_index,
    generate_and_extract_prompts,
    get_indexes_data,
    show_index_options,
    update_session_state_prompt_vars,
)
from components.prompt_expander import prompt_expander_


class IndexPipeline:
    container_naming_rules = """
    Container names must start or end with a letter or number, and can contain only letters, numbers, and the hyphen/minus (-) character.

    Every hyphen/minus (-) character must be immediately preceded and followed by a letter or number; consecutive hyphens aren't permitted in container names.

    All letters in a container name must be lowercase.

    Container names must be from 3 through 63 characters long.
    """
    COLUMN_WIDTHS = [0.275, 0.45, 0.275]

    def __init__(
        self, containers: dict, api_url: str, headers: dict, upload_headers: dict
    ) -> None:
        self.containers = containers
        self.api_url = api_url
        self.headers = headers
        self.upload_headers = upload_headers

    def _parse_container_names(self) -> list:
        """
        Parses the container names from the response from the API.
        """
        container_names = [""]
        try:
            container_names = container_names + self.containers["storage_name"]
        except Exception as e:
            print(f"No data containers found, continuing...\nException: {str(e)}")
        return container_names

    def storage_data_step(self):
        """
        Builds the Storage Data Step for the Indexing Pipeline.
        """
        container_names = self._parse_container_names()

        disable_other_input = False

        _, col2, _ = st.columns(IndexPipeline.COLUMN_WIDTHS)

        with col2:
            st.header(
                "1. Data Storage",
                divider=True,
                help="Upload your own files to a new data storage container, or select an existing data storage created. This step creates a blob container and CosmosDB entry that will contain your data necessary for indexing.",
            )
            select_storage_name = st.selectbox(
                "Select an existing Storage Container.", container_names
            )

            if select_storage_name != "":
                disable_other_input = True
                st.session_state[StorageIndexVars.SELECTED_STORAGE.value] = (
                    select_storage_name
                )
            st.write("Or...")
            with st.expander("Upload data to a storage container."):
                # TODO: validate storage container name before uploading
                # TODO: Add user message that option not available while existing storage container is selected
                input_storage_name = st.text_input(
                    "Enter Storage Name",
                    disabled=disable_other_input,
                    help=IndexPipeline.container_naming_rules,
                )
                input_storage_name = input_storage_name.lower()
                st.session_state[StorageIndexVars.INPUT_STORAGE.value] = (
                    input_storage_name
                )
                file_upload = st.file_uploader(
                    "Upload Data",
                    type=["txt"],
                    accept_multiple_files=True,
                    disabled=disable_other_input,
                )

                if st.button(
                    "Upload Files",
                    disabled=disable_other_input or input_storage_name == "",
                ):
                    if file_upload and input_storage_name != "":
                        file_payloads = []
                        for file in file_upload:
                            file_payload = (
                                "files",
                                (file.name, file.read(), file.type),
                            )
                            file_payloads.append((file_payload))

                        response = requests.post(
                            self.api_url + "/data",
                            headers=self.upload_headers,
                            files=file_payloads,
                            params={"storage_name": input_storage_name},
                        )
                        if response.status_code == 200:
                            st.success("Files uploaded successfully!")
                        else:
                            st.error(f"Error: {json.loads(response.text)}")
                if select_storage_name != "":
                    disable_other_input = True
                    input_storage_name = ""

    def prompt_config_step(self):
        """
        Builds the Prompt Configuration Step for the Indexing Pipeline.
        """
        container_names = self._parse_container_names()
        _, col2, _ = st.columns(IndexPipeline.COLUMN_WIDTHS)
        with col2:
            st.header(
                "2. Generate Prompts",
                divider=True,
                help="Generate fine tuned prompts for the LLM specific to your data and domain.",
            )
            select_storage_name2 = st.selectbox(
                "Select an existing data storage.",
                container_names,
                key="prompt-storage",
            )
            triggered = st.button(label="Generate Prompts", key="prompt-generation")
            if triggered:
                with st.spinner("Generating LLM prompts for GraphRAG..."):
                    generate_and_extract_prompts(
                        api_url=self.api_url,
                        headers=self.headers,
                        storage_name=select_storage_name2,
                    )

                    update_session_state_prompt_vars(initial_setting=True)
                    prompt_keys = [e.value for e in PromptKeys]
                    prompt_values = [st.session_state[k] for k in prompt_keys]
                    if any(prompt_values):
                        prompt_expander_()

    def build_index_step(self):
        """
        Creates the Build Index Step for the Indexing Pipeline.
        """
        _, col2, _ = st.columns(IndexPipeline.COLUMN_WIDTHS)
        with col2:
            st.header(
                "3. Build Index",
                divider=True,
                help="After selecting/creating a data storage container and the LLM prompts, enter an index name and select build index. Building an index will process the data with the LLM create a Knowledge Graph suitable for querying. To track the status of an indexing job, use the check index status below.",
            )
            select_storage_name = st.session_state[
                StorageIndexVars.SELECTED_STORAGE.value
            ]
            input_storage_name = st.session_state[StorageIndexVars.INPUT_STORAGE.value]
            index_name = st.text_input("Enter Index Name")
            st.write(
                f"Selected Storage Container: {select_storage_name} {input_storage_name}"
            )
            if st.button("Build Index"):
                final_storage_name = select_storage_name or input_storage_name
                st.write(final_storage_name)
                entity_prompt = st.session_state[PromptKeys.ENTITY.value]
                summarize_prompt = st.session_state[PromptKeys.SUMMARY.value]
                community_prompt = st.session_state[PromptKeys.COMMUNITY.value]
                print(entity_prompt, summarize_prompt, community_prompt)
                url = self.api_url + "/index"
                response = build_index(
                    api_url=url,
                    headers=self.headers,
                    storage_name=final_storage_name,
                    index_name=index_name,
                    entity_prompt=entity_prompt,
                    summarize_prompt=summarize_prompt,
                    community_prompt=community_prompt,
                )

                if response.status_code == 200:
                    st.success("Job submitted successfully!")
                else:
                    st.error(f"Failed to submit job.\nStatus: {response.text}")

    def check_status_step(self):
        """
        Checks the progress of a running indexing job.
        """
        _, col2, _ = st.columns(IndexPipeline.COLUMN_WIDTHS)
        with col2:
            st.header(
                "4. Check Index Status",
                divider=True,
                help="Select the created index to check status at what steps it is at in indexing. Indexing must be complete in order to be able to execute queries.",
            )

            indexes = get_indexes_data(self.api_url, self.headers)
            options_indexes = show_index_options(indexes)
            index_name_select = st.selectbox(
                "Select an index to check its status.", options_indexes
            )
            progress_bar = st.progress(0, text="Index Job Progress")
            if st.button("Check Status"):
                status_url = self.api_url + f"/index/status/{index_name_select}"
                status_response = requests.get(url=status_url, headers=self.headers)
                status_response_text = json.loads(status_response.text)
                if (
                    status_response.status_code == 200
                    and status_response_text["status"] != ""
                ):
                    try:
                        percent_complete = status_response_text["percent_complete"]
                        st.success(f"Status: {status_response_text['status']}")
                    except Exception as e:
                        print(e)
                    try:
                        progress_bar.progress(float(percent_complete) / 100)
                        st.success(f"Percent Complete: {percent_complete}% ")
                    except Exception as e:
                        print(e)
                    try:
                        progress_status = status_response_text["progress"]
                        st.success(f"Progress: {progress_status } ")
                    except Exception:
                        pass
                else:
                    st.error(f"Status: No workflow associated with {index_name_select}")
