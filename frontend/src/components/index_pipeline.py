# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from io import StringIO

import streamlit as st

from src.components.upload_files_component import upload_files
from src.enums import PromptKeys
from src.functions import GraphragAPI


class IndexPipeline:
    def __init__(self, client: GraphragAPI, column_widths: list[float]) -> None:
        self.client = client
        self.containers = client.get_storage_container_names()
        self.column_widths = column_widths

    def storage_data_step(self):
        """
        Builds the Storage Data Step for the Indexing Pipeline.
        """

        disable_other_input = False
        _, col2, _ = st.columns(self.column_widths)

        with col2:
            st.header(
                "1. Data Storage",
                divider=True,
                help="Select a Data Storage Container to upload data to or select an existing container to use for indexing. The data will be processed by the LLM to create a Knowledge Graph.",
            )
            select_storage_name = st.selectbox(
                label="Select an existing Storage Container.",
                options=[""] + self.containers
                if isinstance(self.containers, list)
                else [],
                key="index-storage",
                index=0,
            )

            if select_storage_name != "":
                disable_other_input = True
            st.write("Or...")
            with st.expander("Upload data to a storage container."):
                # TODO: validate storage container name before uploading
                # TODO: add user message that option not available while existing storage container is selected
                upload_files(
                    self.client,
                    key_prefix="index",
                    disable_other_input=disable_other_input,
                )
                if select_storage_name != "":
                    disable_other_input = True

    def build_index_step(self):
        """
        Creates the Build Index Step for the Indexing Pipeline.
        """
        _, col2, _ = st.columns(self.column_widths)
        with col2:
            st.header(
                "2. Build Index",
                divider=True,
                help="Building an index will process the data from step 1 and create a Knowledge Graph suitable for querying. The LLM will use either the default prompt configuration or the prompts that you generated previously. To track the status of an indexing job, use the check index status below.",
            )
            # use data from either the selected storage container or the uploaded data
            select_storage_name = st.session_state["index-storage"]
            input_storage_name = (
                st.session_state["index-storage-name-input"]
                if st.session_state["index-upload-button"]
                else ""
            )
            storage_selection = select_storage_name or input_storage_name

            # Allow user to choose either default or custom prompts
            custom_prompts = any([st.session_state[k.value] for k in PromptKeys])
            prompt_options = ["Default", "Custom"] if custom_prompts else ["Default"]
            prompt_choice = st.radio(
                "Choose LLM Prompt Configuration",
                options=prompt_options,
                index=1 if custom_prompts else 0,
                key="prompt-config-choice",
                horizontal=True,
            )

            # Create new index name
            index_name = st.text_input("Enter Index Name", key="index-name-input")

            st.write(f"Selected Storage Container: **:blue[{storage_selection}]**")
            if st.button(
                "Build Index",
                help="You must enter both an Index Name and Select a Storage Container to enable this button",
                disabled=not index_name or not storage_selection,
            ):
                entity_prompt = (
                    StringIO(st.session_state[PromptKeys.ENTITY.value])
                    if prompt_choice == "Custom"
                    else None
                )
                summarize_prompt = (
                    StringIO(st.session_state[PromptKeys.SUMMARY.value])
                    if prompt_choice == "Custom"
                    else None
                )
                community_prompt = (
                    StringIO(st.session_state[PromptKeys.COMMUNITY.value])
                    if prompt_choice == "Custom"
                    else None
                )

                response = self.client.build_index(
                    storage_container_name=storage_selection,
                    index_container_name=index_name,
                    entity_extraction_prompt_filepath=entity_prompt,
                    summarize_description_prompt_filepath=summarize_prompt,
                    community_prompt_filepath=community_prompt,
                )

                if response.status_code == 200:
                    st.success(
                        f"Job submitted successfully, using {prompt_choice} prompts!"
                    )
                else:
                    st.error(
                        f"Failed to submit job.\nStatus: {response.json()['detail']}"
                    )

    def check_status_step(self):
        """
        Checks the progress of a running indexing job.
        """
        _, col2, _ = st.columns(self.column_widths)
        with col2:
            st.header(
                "3. Check Index Status",
                divider=True,
                help="Select an index to check the status of what stage indexing is in. Indexing must be complete in order to be able to execute queries.",
            )
            options_indexes = self.client.get_index_names()
            # create logic for defaulting to running job index if one exists
            new_index_name = st.session_state["index-name-input"]
            default_index = (
                options_indexes.index(new_index_name)
                if new_index_name in options_indexes
                else 0
            )
            index_name_select = st.selectbox(
                label="Select an index to check its status.",
                options=options_indexes if any(options_indexes) else [],
                index=default_index,
            )
            progress_bar = st.progress(0, text="Index Job Progress")
            if st.button("Check Status"):
                status_response = self.client.check_index_status(index_name_select)
                if status_response.status_code == 200:
                    status_response_text = status_response.json()
                    if status_response_text["status"] != "":
                        try:
                            # build status message
                            job_status = status_response_text["status"]
                            status_message = f"Status: {status_response_text['status']}"
                            st.success(status_message) if job_status in [
                                "running",
                                "complete",
                            ] else st.warning(status_message)
                        except Exception as e:
                            print(e)
                        try:
                            # build percent complete message
                            percent_complete = status_response_text["percent_complete"]
                            progress_bar.progress(float(percent_complete) / 100)
                            completion_message = (
                                f"Percent Complete: {percent_complete}% "
                            )
                            st.warning(
                                completion_message
                            ) if percent_complete < 100 else st.success(
                                completion_message
                            )
                        except Exception as e:
                            print(e)
                        try:
                            # build progress message
                            progress_status = status_response_text["progress"]
                            progress_status = (
                                progress_status if progress_status else "N/A"
                            )
                            progress_message = f"Progress: {progress_status}"
                            st.success(
                                progress_message
                            ) if progress_status != "N/A" else st.warning(
                                progress_message
                            )
                        except Exception as e:
                            print(e)
                    else:
                        st.warning(
                            f"No status information available for this index: {index_name_select}"
                        )
                else:
                    st.warning(
                        f"No workflow information available for this index: {index_name_select}"
                    )
