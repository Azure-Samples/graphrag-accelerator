# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import pytest

from src.api.common import (
    retrieve_original_blob_container_name,
    sanitize_name,
    validate_blob_container_name,
    validate_index_file_exist,
)


def test_validate_blob_container_name():
    """Test the src.api.common.validate_blob_container_name function."""
    # test valid container name
    assert validate_blob_container_name("validcontainername") is None
    # test invalid container name
    with pytest.raises(ValueError):
        validate_blob_container_name("invalidContainerName")
    with pytest.raises(ValueError):
        validate_blob_container_name(
            "invalidcontainernameinvalidcontainernameinvalidcontainerinvalids"
        )
    with pytest.raises(ValueError):
        validate_blob_container_name("*invalidContainerName")
    with pytest.raises(ValueError):
        validate_blob_container_name("invalid+ContainerName")
    with pytest.raises(ValueError):
        validate_blob_container_name("invalid--containername")
    with pytest.raises(ValueError):
        validate_blob_container_name("invalidcontainername-")


def test_retrieve_original_blob_container_name(container_with_graphml_file):
    """Test the src.api.common.retrieve_original_blob_container_name function."""
    # test retrieving a valid container name
    original_name = container_with_graphml_file
    sanitized_name = sanitize_name(original_name)
    assert retrieve_original_blob_container_name(sanitized_name) == original_name
    # test retrieving an invalid container name
    assert retrieve_original_blob_container_name("nonexistent-container") is None


def test_validate_index_file_exist(container_with_graphml_file):
    """Test the src.api.common.validate_index_file_exist function."""
    original_name = container_with_graphml_file
    sanitized_name = sanitize_name(original_name)
    # test with a valid index and valid file
    assert (
        validate_index_file_exist(sanitized_name, "output/summarized_graph.graphml")
        is None
    )
    # test with a valid index and non-existent file
    with pytest.raises(ValueError):
        validate_index_file_exist(sanitized_name, "non-existent-file")
    # test non-existent index and valid file
    with pytest.raises(ValueError):
        validate_index_file_exist(
            "nonexistent-index", "output/summarized_graph.graphml"
        )
