# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import inspect
import os
import shutil
import uuid

import pytest
import requests
import wikipedia
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

load_dotenv()


def _upload_files(blob_service_client, directory, container_name):
    for root, dirs, files in os.walk(directory):
        for file in files:
            local_path = os.path.join(root, file)
            relative_path = os.path.relpath(local_path, directory)
            # replace backslashes with forward slashes (for Windows compatibility)
            relative_path = relative_path.replace("\\", "/")
            # upload file
            blob_client = blob_service_client.get_blob_client(
                blob=relative_path, container=container_name
            )
            with open(local_path, "rb") as data:
                blob_client.upload_blob(
                    data, connection_timeout=120
                )  # increase timeout for large files


@pytest.fixture(scope="session")
def client(request):
    """Return the session base url which is the deployment url authorized with the apim subscription key stored in your .env file"""
    deployment_url = os.environ["DEPLOYMENT_URL"]
    deployment_url = deployment_url.rstrip("/")
    apim_key = os.environ["APIM_SUBSCRIPTION_KEY"]
    session = requests.Session()
    session.headers.update({"Ocp-Apim-Subscription-Key": apim_key})
    session.base_url = deployment_url
    return session


@pytest.fixture()
def prepare_valid_index_data():
    """Prepare valid test data by uploading the result files of a "valid" indexing run to a new blob container."""
    account_url = os.environ["STORAGE_ACCOUNT_BLOB_URL"]
    credential = DefaultAzureCredential()
    blob_service_client = BlobServiceClient(account_url, credential=credential)

    # generate a unique data container name
    container_name = "test-data-" + str(uuid.uuid4())
    container_name = container_name.replace("_", "-").replace(".", "-").lower()[:63]
    blob_service_client.create_container(container_name)
    this_directory = os.path.dirname(
        os.path.abspath(inspect.getfile(inspect.currentframe()))
    )
    # generate a unique index container name
    index_name = "test-index-" + str(uuid.uuid4())
    index_name = index_name.replace("_", "-").replace(".", "-").lower()[:63]
    blob_service_client.create_container(index_name)
    this_directory = os.path.dirname(
        os.path.abspath(inspect.getfile(inspect.currentframe()))
    )
    # use a small amount of sample text to test the data upload endpoint
    page = wikipedia.page("Alaska")
    os.makedirs(f"{this_directory}/data/sample-data", exist_ok=True)
    with open(f"{this_directory}/data/sample-data/sample_text.txt", "w") as f:
        f.write(page.summary)
    _upload_files(
        blob_service_client,
        f"{this_directory}/data/sample-data",
        container_name,
    )
    _upload_files(blob_service_client, f"{this_directory}/data/test-index", index_name)

    endpoint = os.environ["COSMOS_URI_ENDPOINT"]
    credential = DefaultAzureCredential()
    client = CosmosClient(endpoint, credential)

    container_store = "container-store"
    database = client.get_database_client(container_store)
    container_container = database.get_container_client(container_store)

    index_item = {"id": index_name, "type": "index"}
    data_item = {"id": container_name, "type": "data"}
    container_container.create_item(body=index_item)
    container_container.create_item(body=data_item)

    container_store = "jobs"
    database = client.get_database_client(container_store)
    container_jobs = database.get_container_client(container_store)

    index_item = {
        "id": index_name,
        "index_name": index_name,
        "storage_name": container_name,
        "all_workflows": [
            "create_base_text_units",
            "create_final_text_units",
            "create_base_extracted_entities",
            "create_summarized_entities",
            "create_base_entity_graph",
            "create_final_entities",
            "create_final_relationships",
            "create_base_documents",
            "create_base_document_graph",
            "create_final_documents",
            "create_final_communities",
            "create_final_community_reports",
            "create_final_covariates",
            "create_base_entity_nodes",
            "create_base_document_nodes",
            "create_final_nodes",
        ],
        "completed_workflows": [
            "create_base_text_units",
            "create_base_extracted_entities",
            "create_final_covariates",
            "create_summarized_entities",
            "create_base_entity_graph",
            "create_final_entities",
            "create_final_relationships",
            "create_final_communities",
            "create_final_community_reports",
            "create_base_entity_nodes",
            "create_final_text_units",
            "create_base_documents",
            "create_base_document_graph",
            "create_base_document_nodes",
            "create_final_documents",
            "create_final_nodes",
        ],
        "failed_workflows": [],
        "status": "complete",
        "percent_complete": 100,
        "progress": "16 out of 16 workflows completed successfully.",
    }
    container_jobs.create_item(body=index_item)

    yield index_name  # test runs here

    # clean up
    blob_service_client.delete_container(container_name)
    blob_service_client.delete_container(index_name)
    container_container.delete_item(item=container_name, partition_key=container_name)
    container_jobs.delete_item(item=index_name, partition_key=index_name)
    shutil.rmtree(f"{this_directory}/data/sample-data")


@pytest.fixture()
def prepare_invalid_index_data():
    """Prepare valid test data by uploading the result files of a "valid" indexing run to a new blob container."""
    account_url = os.environ["STORAGE_ACCOUNT_BLOB_URL"]
    credential = DefaultAzureCredential()
    blob_service_client = BlobServiceClient(account_url, credential=credential)

    # generate a unique data container name
    container_name = "test-index-pytest-" + str(uuid.uuid4())
    container_name = container_name.replace("_", "-").replace(".", "-").lower()[:63]
    blob_service_client.create_container(container_name)
    this_directory = os.path.dirname(
        os.path.abspath(inspect.getfile(inspect.currentframe()))
    )
    _upload_files(
        blob_service_client, f"{this_directory}/data/test-index", container_name
    )

    blob_client = blob_service_client.get_blob_client(
        container=container_name, blob="embedded_graph.1.graphml"
    )
    blob_client.delete_blob()

    endpoint = os.environ["COSMOS_URI_ENDPOINT"]
    credential = DefaultAzureCredential()
    client = CosmosClient(endpoint, credential)

    container_store = "container-store"
    database = client.get_database_client(container_store)
    container_container = database.get_container_client(container_store)
    index_item = {"id": container_name, "type": "index"}
    container_container.create_item(body=index_item)

    container_store = "jobs"
    database = client.get_database_client(container_store)
    container_jobs = database.get_container_client(container_store)
    index_item = {
        "id": container_name,
        "storage_name": "data1",
        "task_state": "15 steps out of 15 completed.",
        "percent_complete": "100.0",
    }
    container_jobs.create_item(body=index_item)

    yield container_name  # test runs here

    # clean up
    blob_service_client.delete_container(container_name)
    container_container.delete_item(item=container_name, partition_key=container_name)
    container_jobs.delete_item(item=container_name, partition_key=container_name)


# this fixture tests the creation of an entity configuration, not good practice but it's needed for the other tests
@pytest.fixture
def create_entity_configuration(client):
    endpoint = "/pipeline/config"
    entity_configuration_name = str(uuid.uuid4())
    entity_types = ["ORGANIZATION"]
    entity_examples = [
        {
            "Entity_types": "ORGANIZATION",
            "Text": "Arm's (ARM) stock skyrocketed...",
            "Output": '("entity"{tuple_delimiter}ARM{tuple_delimiter}ORGANIZATION{tuple_delimiter}...)',
        }
    ]
    request_data = {
        "entityConfigurationName": entity_configuration_name,
        "entityTypes": entity_types,
        "entityExamples": entity_examples,
    }
    response = client.post(
        url=f"{client.base_url}{endpoint}/entity/types", json=request_data
    )
    assert response.status_code == 200
    yield entity_configuration_name


@pytest.fixture
def data_upload_small(client):
    this_directory = os.path.dirname(
        os.path.abspath(inspect.getfile(inspect.currentframe()))
    )
    # use a small amount of sample text to test the data upload endpoint
    page = wikipedia.page("Alaska")
    with open(f"{this_directory}/data/sample_text.txt", "w") as f:
        f.write(page.summary)

    # test the upload of data
    files = [("files", open(f"{this_directory}/data/sample_text.txt", "rb"))]
    assert len(files) > 0
    blob_container_name = f"test-data-{str(uuid.uuid4())}"
    print(f"Creating blob data container: {blob_container_name}")
    response = client.post(
        url=f"{client.base_url}/data",
        files=files,
        params={"storage_name": blob_container_name},
    )
    assert response.status_code == 200

    yield blob_container_name  # test runs here

    # clean up
    os.remove(f"{this_directory}/data/sample_text.txt")
    print(f"Deleting blob data container: {blob_container_name}")
    response = client.delete(url=f"{client.base_url}/data/{blob_container_name}")
    assert response.status_code == 200
