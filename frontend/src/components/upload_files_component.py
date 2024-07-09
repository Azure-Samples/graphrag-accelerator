# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json

import streamlit as st

from src.graphrag_api import GraphragAPI

UPLOAD_HELP_MESSAGE = """
This functionality is disabled while an existing Storage Container is selected.
Please deselect the existing Storage Container to upload new data.
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
        help=UPLOAD_HELP_MESSAGE,
    )
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
