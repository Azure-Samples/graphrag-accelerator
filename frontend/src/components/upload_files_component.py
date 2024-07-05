import json

import streamlit as st

from src.enums import StorageIndexVars
from src.graphrag_api import GraphragAPI

CONTAINER_NAMING_RULES = """
Container names must start or end with a letter or number, and can contain only letters, numbers, and the hyphen/minus (-) character.

Every hyphen/minus (-) character must be immediately preceded and followed by a letter or number; consecutive hyphens aren't permitted in container names.

All letters in a container name must be lowercase.

Container names must be from 3 through 63 characters long.
"""


def upload_files(
    client: GraphragAPI, key_prefix: str, disable_other_input: bool = False
):
    """
    Reusable component to upload files to Blob Storage Container
    """
    input_storage_name = st.text_input(
        label="Enter Storage Name",
        key=f"{key_prefix}-storage-name-input",
        disabled=disable_other_input,
        help=CONTAINER_NAMING_RULES,
    )

    input_storage_name = input_storage_name.lower()
    st.session_state[StorageIndexVars.INPUT_STORAGE.value] = input_storage_name
    file_upload = st.file_uploader(
        "Upload Data",
        type=["txt"],
        key=f"{key_prefix}-file-uploader",
        accept_multiple_files=True,
        disabled=disable_other_input,
    )

    uploaded = st.button(
        "Upload Files",
        key=f"{key_prefix}-upload-button",
        disabled=disable_other_input or input_storage_name == "",
    )
    if uploaded:
        if file_upload and input_storage_name != "":
            file_payloads = []
            for file in file_upload:
                file_payload = (
                    "files",
                    (file.name, file.read(), file.type),
                )
                file_payloads.append((file_payload))

            response = client.upload_files(file_payloads, input_storage_name)
            if response.status_code == 200:
                st.success("Files uploaded successfully!")
            else:
                st.error(f"Error: {json.loads(response.text)}")
    return uploaded
