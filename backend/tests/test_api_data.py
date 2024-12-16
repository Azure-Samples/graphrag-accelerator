# def test_upload_files(client):
#     # create a sample file
#     with open("test.txt", "wb") as f:
#         f.write(b"Hello, world!")

#     # send the file in the request
#     with open("test.txt", "rb") as f:
#         response = client.post(
#             "/data",
#             files={"file": ("test.txt", f, "text/plain")},
#             params={"storage_name": "testContainer"},
#         )

#     # check the response
#     print("data upload response")
#     print(response.json())
#     assert response.status_code == 200


def test_get_list_of_data_containers(setup_cosmos, client):
    response = client.get("/data")
    assert response.status_code == 200
