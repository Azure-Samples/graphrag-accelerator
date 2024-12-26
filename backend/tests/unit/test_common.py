# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import pytest

from src.api.common import (
    validate_blob_container_name,
)


def test_validate_blob_container_name():
    """Test the src.api.common.validate_blob_container_name function."""
    # test valid container name
    assert validate_blob_container_name("validcontainername") is None
    # test invalid container name
    with pytest.raises(ValueError):
        validate_blob_container_name("invalidContainerName")
    with pytest.raises(ValueError):
        validate_blob_container_name("*invalidContainerName")
    with pytest.raises(ValueError):
        validate_blob_container_name("invalid+ContainerName")
    with pytest.raises(ValueError):
        validate_blob_container_name("invalid--ContainerName")
    with pytest.raises(ValueError):
        validate_blob_container_name("invalidContainerName-")


# def test_validate_index_file_exist():
#     """Test the src.api.common.validate_index_file_exist function."""
#     # test valid index and file
#     assert validate_index_file_exist("validindex", "validfile") is None
#     # test invalid index
#     with pytest.raises(ValueError):
#         validate_index_file_exist("invalidindex", "validfile")
#     # test invalid file
#     with pytest.raises(ValueError):
#         validate_index_file_exist("validindex", "invalidfile")
#     # test invalid index and file
#     with pytest.raises(ValueError):
#         validate_index_file_exist("invalidindex", "invalidfile")
