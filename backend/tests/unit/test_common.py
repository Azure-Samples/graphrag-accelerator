# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import pytest

from graphrag_app.utils.common import (
    desanitize_name,
    sanitize_name,
    validate_index_file_exist,
)


def test_desanitize_name(container_with_graphml_file):
    """Test the graphrag_app.utils.common.desanitize_name function."""
    # test retrieving a valid container name
    original_name = container_with_graphml_file
    sanitized_name = sanitize_name(original_name)
    assert desanitize_name(sanitized_name) == original_name
    # test retrieving an invalid container name
    assert desanitize_name("nonexistent-container") is None


def test_validate_index_file_exist(container_with_graphml_file):
    """Test the graphrag_app.utils.common.validate_index_file_exist function."""
    original_name = container_with_graphml_file
    sanitized_name = sanitize_name(original_name)
    # test with a valid index and valid file
    assert validate_index_file_exist(sanitized_name, "output/graph.graphml") is None
    # test with a valid index and non-existent file
    with pytest.raises(ValueError):
        validate_index_file_exist(sanitized_name, "non-existent-file")
    # test non-existent index and valid file
    with pytest.raises(ValueError):
        validate_index_file_exist("nonexistent-index", "output/graph.graphml")
