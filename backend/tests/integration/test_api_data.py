"""
Integration tests for the /data API endpoints.
"""

import os


def test_upload_files(setup_cosmos, client):
    # create a single file
    with open("test.txt", "wb") as f:
        f.write(b"Hello, world!")

    # send the file in the request
    with open("test.txt", "rb") as f:
        response = client.post(
            "/data",
            files={"files": ("test.txt", f)},
            params={"storage_name": "testContainer"},
        )

    # check the response
    print("data upload response")
    assert response.status_code == 200

    # remove the sample file as part of garbage collection
    if os.path.exists("test.txt"):
        os.remove("test.txt")


def test_delete_files(setup_cosmos, client):
    # delete a data blob container
    response = client.delete("/data/testContainer")
    assert response.status_code == 200


def test_get_list_of_data_containers(setup_cosmos, client):
    response = client.get("/data")
    assert response.status_code == 200
