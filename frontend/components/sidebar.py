import json

import requests
import streamlit as st

# sys.path.append("..")
from .functions import (
    generate_and_extract_prompts,
    show_index_options,
    update_session_state_prompt_vars,
)
from .prompt_expander import prompt_expander_


def sidebar_layout(
    data: dict, api_url: str, headers: dict, headers_upload: dict, indexes: dict
):
    """
    Returns code for sidebar layout.
    """
    with st.container(border=True):
        st.title("Index Pipeline")
        # image = Image.open("./static/Microsoft_logo.png")
        # st.sidebar.image(image, width=200)
        data_containers = [""]
        try:
            data_containers = data_containers + data["storage_name"]
        except Exception as e:
            print(f"No data containers found, continuing...\nException: {str(e)}")

        disable_other_input = False

        st.header(
            "1. Data Storage",
            divider=True,
            help="Upload your own files to a new data storage container, or select an existing data storage created. This step creates a blob container and CosmosDB entry that will contain your data necessary for indexing.",
        )

        select_storage_name = st.sidebar.selectbox(
            "Select an existing data storage.", data_containers
        )

        if select_storage_name != "":
            disable_other_input = True

        with st.expander("Upload data to a storage container."):
            input_storage_name = st.text_input(
                "Enter Storage Name", disabled=disable_other_input
            )
            file_upload = st.file_uploader(
                "Upload Data",
                type=["txt"],
                accept_multiple_files=True,
                disabled=disable_other_input,
            )

            if st.button(
                "Upload Files", disabled=disable_other_input or input_storage_name == ""
            ):
                if file_upload and input_storage_name != "":
                    file_payloads = []
                    for file in file_upload:
                        file_payload = ("files", (file.name, file.read(), file.type))
                        file_payloads.append((file_payload))

                    response = requests.post(
                        api_url + "/data",
                        headers=headers_upload,
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

        st.header(
            "2. Generate Prompts",
            divider=True,
            help="Generate fine tuned prompts for the LLM specific to your data and domain.",
        )
        select_storage_name2 = st.selectbox(
            "Select an existing data storage.", data_containers, key="something-unique"
        )
        triggered = st.button(label="Generate Prompts", key="prompt-generation")
        if triggered:
            generate_and_extract_prompts(
                api_url=api_url,
                headers=headers,
                storage_name=select_storage_name2,
            )
            update_session_state_prompt_vars(initial_setting=True)
            prompt_expander_()
        # try:
        #     st.session_state["entity_config"] = ["DEFAULT"] + get_entity_data(
        #         api_url, headers
        #     )["entity_configuration_name"]
        # except Exception as e:
        #     st.session_state.entity_config = [""]
        #     print(f"No entity configurations found, continuing...\nException: {str(e)}")

        # disable_entity_input = False
        # st.session_state.update(st.session_state)
        # entity_config_name_select = st.sidebar.selectbox(
        #     "Select an existing entity configuration.",
        #     st.session_state["entity_config"],
        #     index=0,
        #     key="entity_select_key",
        # )

        # if entity_config_name_select != "DEFAULT":
        #     disable_entity_input = True

        # with st.expander("Create new entity configuration"):
        #     if "entity_examples" not in st.session_state:
        #         st.session_state["entity_examples"] = []

        #     with open("./entity_config.json", "r") as file:
        #         entity_data = json.load(file)
        #     entity_data = json.dumps(entity_data)

        #     entity_config_json = st.text_area(
        #         "Raw Entity Config Json",
        #         value=entity_data,
        #         disabled=disable_entity_input,
        #     )

        #     if st.button(
        #         "Create Entity Configuration from JSON", disabled=disable_entity_input
        #     ):
        #         url = api_url + "/index/config/entity"
        #         parsed_json = json.loads(entity_config_json)
        #         response = requests.post(url, json=parsed_json, headers=headers)
        #         if response.status_code == 200:
        #             st.success("Entity configuration created successfully!")
        #             new_entity_json = [parsed_json.get("entity_configuration_name", [])]
        #             st.session_state["entity_config"] += new_entity_json

        #             print(st.session_state.entity_config)
        #         else:
        #             st.error(
        #                 f"Failed to create entity configuration. {json.loads(response.text)['detail']}"
        #             )

        st.header(
            "3. Build Index",
            divider=True,
            help="After selecting/creating a data storage and entity configuration, enter an index name and select build index. Building an index will process the data with the LLM to be in a proper format for querying. To track the status of an indexing job, use the check index status below.",
        )
        index_name = st.text_input("Enter Index Name")
        st.write(
            f"Selected Storage Container: {select_storage_name} {input_storage_name}"
        )
        entity_config_name_select = "Entity Config JSON"
        st.write(f"Selected Entity Config:  {entity_config_name_select}")
        if st.button("Build Index"):
            if select_storage_name != "":
                final_storage_name = select_storage_name
            elif input_storage_name != "":
                final_storage_name = input_storage_name

            if entity_config_name_select != "":
                final_entity_name = entity_config_name_select
            if (
                final_entity_name == "DEFAULT"
            ):  # no entity config selected, so creating and using the default config at runtime.
                request = {
                    "storage_name": final_storage_name,
                    "index_name": index_name,
                }
            else:
                request = {
                    "storage_name": final_storage_name,
                    "index_name": index_name,
                    "entity_config_name": final_entity_name,
                }

            url = api_url + "/index"

            response = requests.post(url, json=request, headers=headers)

            if response.status_code == 200:
                st.success("Job submitted successfully!")
            else:
                st.error(f"Failed to submit job.\nStatus: {response.text}")
        st.divider()
        st.header(
            "Check Index Status",
            divider=True,
            help="Select the created index to check status at what steps it is at in indexing. Indexing must be complete in order to be able to query properly.",
        )

        options_indexes = show_index_options(indexes)
        index_name_select = st.sidebar.selectbox(
            "Select an index to check its status.", options_indexes
        )

        progress_bar = st.progress(0)

        if st.button("Check Status"):
            status_url = api_url + f"/index/status/{index_name_select}"
            status_response = requests.get(url=status_url, headers=headers)
            status_response_text = json.loads(status_response.text)
            if (
                status_response.status_code == 200
                and status_response_text["status"] != ""
            ):
                try:
                    percent_complete = status_response_text["percent_complete"]
                    st.success(f"Status: {status_response_text['status']}")
                except Exception as e:
                    print(f"Error: {str(e)}")
                try:
                    progress_bar.progress(float(percent_complete) / 100)
                    st.success(f"Percent Complete: {percent_complete}% ")
                except Exception as e:
                    print(f"Error: {str(e)}")
                try:
                    progress_status = status_response_text["progress"]
                    st.success(f"Progress: {progress_status } ")
                except Exception as e:
                    print(f"Error: {str(e)}")
            else:
                st.error(f"Status: No workflow associated with {index_name}")
