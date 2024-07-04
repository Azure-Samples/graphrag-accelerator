import json
from io import StringIO

import streamlit as st

from src.app_utilities.enums import PromptKeys, StorageIndexVars
from src.app_utilities.functions import GraphragAPI
from src.components.upload_files_component import upload_files


class IndexPipeline:
    container_naming_rules = """
    Container names must start or end with a letter or number, and can contain only letters, numbers, and the hyphen/minus (-) character.

    Every hyphen/minus (-) character must be immediately preceded and followed by a letter or number; consecutive hyphens aren't permitted in container names.

    All letters in a container name must be lowercase.

    Container names must be from 3 through 63 characters long.
    """
    COLUMN_WIDTHS = [0.275, 0.45, 0.275]

    def __init__(self, client: GraphragAPI) -> None:
        self.client = client
        self.containers = client.get_storage_container_names()

    def storage_data_step(self):
        """
        Builds the Storage Data Step for the Indexing Pipeline.
        """

        disable_other_input = False
        _, col2, _ = st.columns(IndexPipeline.COLUMN_WIDTHS)

        with col2:
            st.header(
                "1. Data Storage",
                divider=True,
                help="Select a Data Storage Container to upload data to or select an existing container to use for indexing. The data will be processed by the LLM to create a Knowledge Graph.",
            )
            select_storage_name = st.selectbox(
                label="Select an existing Storage Container.",
                options=self.containers if any(self.containers) else [],
                key="index-storage",
                index=0,
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
                upload_files(
                    self.client,
                    key_prefix="index",
                    disable_other_input=disable_other_input,
                )

                if select_storage_name != "":
                    disable_other_input = True
                    # input_storage_name = ""

    def prompt_selection_step(self):
        raise NotImplementedError(
            "This is an optional method that has not been implemented yet."
        )
        # _, col2, _ = st.columns(IndexPipeline.COLUMN_WIDTHS)
        # with col2:
        #     st.header(
        #         "2. Select LLM Prompts",
        #         divider=True,
        #         help="Generate fine tuned prompts for the LLM specific to your data and domain.",
        #     )
        #     selection = st.radio(
        #         label="Prompt Selection",
        #         captions=[
        #             "Use the built-in default prompts",
        #             "Use the generated prompts from Steps 1 + 2",
        #         ],
        #         label_visibility="hidden",
        #         options=["Use Default Prompts", "Use Generated Prompts"],
        #         index=1,
        #         key="prompt-radio",
        #     )
        #     _ = selection

    def build_index_step(self):
        """
        Creates the Build Index Step for the Indexing Pipeline.
        """
        _, col2, _ = st.columns(IndexPipeline.COLUMN_WIDTHS)
        with col2:
            st.header(
                "2. Build Index",
                divider=True,
                help="Building an index will process the data from step 1 and create a Knowledge Graph suitable for querying. The LLM will use either the default prompt configuration or the prompts that you generated previously. To track the status of an indexing job, use the check index status below.",
            )
            select_storage_name = st.session_state[
                StorageIndexVars.SELECTED_STORAGE.value
            ]
            input_storage_name = st.session_state[StorageIndexVars.INPUT_STORAGE.value]
            index_name = st.text_input("Enter Index Name")
            st.write(
                f"Selected Storage Container: :blue[{select_storage_name}] {input_storage_name}"
            )
            if st.button("Build Index"):
                final_storage_name = select_storage_name or input_storage_name
                entity_prompt = StringIO(st.session_state[PromptKeys.ENTITY.value])
                summarize_prompt = StringIO(st.session_state[PromptKeys.SUMMARY.value])
                community_prompt = StringIO(
                    st.session_state[PromptKeys.COMMUNITY.value]
                )

                response = self.client.build_index(
                    storage_name=final_storage_name,
                    index_name=index_name,
                    entity_extraction_prompt_filepath=entity_prompt,
                    summarize_description_prompt_filepath=summarize_prompt,
                    community_prompt_filepath=community_prompt,
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
                "3. Check Index Status",
                divider=True,
                help="Select the created index to check status at what steps it is at in indexing. Indexing must be complete in order to be able to execute queries.",
            )

            options_indexes = self.client.get_index_names()
            index_name_select = st.selectbox(
                label="Select an index to check its status.",
                options=options_indexes if any(options_indexes) else [],
            )
            progress_bar = st.progress(0, text="Index Job Progress")
            if st.button("Check Status"):
                status_response = self.client.check_index_status(index_name_select)
                status_response_text: dict = json.loads(status_response.text)
                if (
                    status_response.status_code == 200
                    and status_response_text["status"] != ""
                ):
                    try:
                        job_status = status_response_text["status"]
                        status_message = f"Status: {status_response_text['status']}"
                        _ = (
                            st.success(status_message)
                            if job_status in ["running", "complete"]
                            else st.warning(status_message)
                        )
                    except Exception as e:
                        print(e)
                    try:
                        percent_complete = status_response_text["percent_complete"]
                        progress_bar.progress(float(percent_complete) / 100)
                        completion_message = f"Percent Complete: {percent_complete}% "
                        _ = (
                            st.warning(completion_message)
                            if percent_complete < 100
                            else st.success(completion_message)
                        )
                    except Exception as e:
                        print(e)
                    try:
                        progress_status = status_response_text["progress"]
                        progress_status = progress_status if progress_status else "N/A"
                        progress_message = f"Progress: {progress_status}"
                        _ = (
                            st.success(progress_message)
                            if progress_status != "N/A"
                            else st.warning(progress_message)
                        )
                    except Exception as e:
                        print(e)
                else:
                    st.error(f"Status: No workflow associated with {index_name_select}")
