# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import time
import uuid

import pytest

index_endpoint = "/index"


@pytest.fixture
def create_entity_config(client):
    entity_config_name = f"default-{str(uuid.uuid4())}"
    entity_types = ["ORGANIZATION", "GEO", "PERSON"]
    entity_examples = [
        {
            "entity_types": "ORGANIZATION, PERSON",
            "text": "The Fed is scheduled to meet on Tuesday and Wednesday, with the central bank planning to release its latest policy decision on Wednesday at 2:00 p.m. ET, followed by a press conference where Fed Chair Jerome Powell will take questions. Investors expect the Federal Open Market Committee to hold its benchmark interest rate steady in a range of 5.25%-5.5%.",
            "output": '("entity"{tuple_delimiter}FED{tuple_delimiter}ORGANIZATION{tuple_delimiter}The Fed is the Federal Reserve, which will set interest rates on Tuesday and Wednesday)\n{record_delimiter}\n("entity"{tuple_delimiter}JEROME POWELL{tuple_delimiter}PERSON{tuple_delimiter}Jerome Powell is the chair of the Federal Reserve)\n{record_delimiter}\n("entity"{tuple_delimiter}FEDERAL OPEN MARKET COMMITTEE{tuple_delimiter}ORGANIZATION{tuple_delimiter}The Federal Reserve committee makes key decisions about interest rates and the growth of the United States money supply)\n{record_delimiter}\n("relationship"{tuple_delimiter}JEROME POWELL{tuple_delimiter}FED{tuple_delimiter}Jerome Powell is the Chair of the Federal Reserve and will answer questions at a press conference{tuple_delimiter}9)\n{completion_delimiter}',
        },
        {
            "entity_types": "ORGANIZATION",
            "text": "Arm's (ARM) stock skyrocketed in its opening day on the Nasdaq Thursday. But IPO experts warn that the British chipmaker's debut on the public markets isn't indicative of how other newly listed companies may perform.\n\nArm, a formerly public company, was taken private by SoftBank in 2016. The well-established chip designer says it powers 99% of premium smartphones.",
            "output": '("entity"{tuple_delimiter}ARM{tuple_delimiter}ORGANIZATION{tuple_delimiter}Arm is a stock now listed on the Nasdaq which powers 99% of premium smartphones)\n{record_delimiter}\n("entity"{tuple_delimiter}SOFTBANK{tuple_delimiter}ORGANIZATION{tuple_delimiter}SoftBank is a firm that previously owned Arm)\n{record_delimiter}\n("relationship"{tuple_delimiter}ARM{tuple_delimiter}SOFTBANK{tuple_delimiter}SoftBank formerly owned Arm from 2016 until present{tuple_delimiter}5)\n{completion_delimiter}',
        },
        {
            "entity_types": "ORGANIZATION,GEO,PERSON",
            "text": "Five Americans jailed for years in Iran and widely regarded as hostages are on their way home to the United States.\n\nThe last pieces in a controversial swap mediated by Qatar fell into place when $6bn (£4.8bn) of Iranian funds held in South Korea reached banks in Doha.\n\nIt triggered the departure of the four men and one woman in Tehran, who are also Iranian citizens, on a chartered flight to Qatar's capital.\n\nThey were met by senior US officials and are now on their way to Washington.\n\nThe Americans include 51-year-old businessman Siamak Namazi, who has spent nearly eight years in Tehran's notorious Evin prison, as well as businessman Emad Shargi, 59, and environmentalist Morad Tahbaz, 67, who also holds British nationality.",
            "output": '("entity"{tuple_delimiter}IRAN{tuple_delimiter}GEO{tuple_delimiter}Iran held American citizens as hostages)\n{record_delimiter}\n("entity"{tuple_delimiter}UNITED STATES{tuple_delimiter}GEO{tuple_delimiter}Country seeking to release hostages)\n{record_delimiter}\n("entity"{tuple_delimiter}QATAR{tuple_delimiter}GEO{tuple_delimiter}Country that negotiated a swap of money in exchange for hostages)\n{record_delimiter}\n("entity"{tuple_delimiter}SOUTH KOREA{tuple_delimiter}GEO{tuple_delimiter}Country holding funds from Iran)\n{record_delimiter}\n("entity"{tuple_delimiter}TEHRAN{tuple_delimiter}GEO{tuple_delimiter}Capital of Iran where the Iranian hostages were being held)\n{record_delimiter}\n("entity"{tuple_delimiter}DOHA{tuple_delimiter}GEO{tuple_delimiter}Capital city in Qatar)\n{record_delimiter}\n("entity"{tuple_delimiter}WASHINGTON{tuple_delimiter}GEO{tuple_delimiter}Capital city in United States)\n{record_delimiter}\n("entity"{tuple_delimiter}SIAMAK NAMAZI{tuple_delimiter}PERSON{tuple_delimiter}Hostage who spent time in Tehran\'s Evin prison)\n{record_delimiter}\n("entity"{tuple_delimiter}EVIN PRISON{tuple_delimiter}GEO{tuple_delimiter}Notorious prison in Tehran)\n{record_delimiter}\n("entity"{tuple_delimiter}EMAD SHARGI{tuple_delimiter}PERSON{tuple_delimiter}Businessman who was held hostage)\n{record_delimiter}\n("entity"{tuple_delimiter}MORAD TAHBAZ{tuple_delimiter}PERSON{tuple_delimiter}British national and environmentalist who was held hostage)\n{record_delimiter}\n("relationship"{tuple_delimiter}IRAN{tuple_delimiter}UNITED STATES{tuple_delimiter}Iran negotiated a hostage exchange with the United States{tuple_delimiter}2)\n{record_delimiter}\n("relationship"{tuple_delimiter}QATAR{tuple_delimiter}UNITED STATES{tuple_delimiter}Qatar brokered the hostage exchange between Iran and the United States{tuple_delimiter}2)\n{record_delimiter}\n("relationship"{tuple_delimiter}QATAR{tuple_delimiter}IRAN{tuple_delimiter}Qatar brokered the hostage exchange between Iran and the United States{tuple_delimiter}2)\n{record_delimiter}\n("relationship"{tuple_delimiter}SIAMAK NAMAZI{tuple_delimiter}EVIN PRISON{tuple_delimiter}Siamak Namazi was a prisoner at Evin prison{tuple_delimiter}8)\n{record_delimiter}\n("relationship"{tuple_delimiter}SIAMAK NAMAZI{tuple_delimiter}MORAD TAHBAZ{tuple_delimiter}Siamak Namazi and Morad Tahbaz were exchanged in the same hostage release{tuple_delimiter}2)\n{record_delimiter}\n("relationship"{tuple_delimiter}SIAMAK NAMAZI{tuple_delimiter}EMAD SHARGI{tuple_delimiter}Siamak Namazi and Emad Shargi were exchanged in the same hostage release{tuple_delimiter}2)\n{record_delimiter}\n("relationship"{tuple_delimiter}MORAD TAHBAZ{tuple_delimiter}EMAD SHARGI{tuple_delimiter}Morad Tahbaz and Emad Shargi were exchanged in the same hostage release{tuple_delimiter}2)\n{record_delimiter}\n("relationship"{tuple_delimiter}SIAMAK NAMAZI{tuple_delimiter}IRAN{tuple_delimiter}Siamak Namazi was a hostage in Iran{tuple_delimiter}2)\n{record_delimiter}\n("relationship"{tuple_delimiter}MORAD TAHBAZ{tuple_delimiter}IRAN{tuple_delimiter}Morad Tahbaz was a hostage in Iran{tuple_delimiter}2)\n{record_delimiter}\n("relationship"{tuple_delimiter}EMAD SHARGI{tuple_delimiter}IRAN{tuple_delimiter}Emad Shargi was a hostage in Iran{tuple_delimiter}2)\n{completion_delimiter}',
        },
    ]
    request_data = {
        "entity_configuration_name": entity_config_name,
        "entity_types": entity_types,
        "entity_examples": entity_examples,
    }
    response = client.post(
        url=f"{client.base_url}{index_endpoint}/config/entity", json=request_data
    )
    yield (entity_config_name, response)


def test_create_delete_entity_config(client, create_entity_config):
    entity_config_name, response = create_entity_config
    assert response.status_code == 200
    response = client.delete(
        url=f"{client.base_url}{index_endpoint}/{entity_config_name}"
    )
    assert response.status_code == 200


@pytest.fixture
def index_create(client, data_upload_small):
    blob_container_name = data_upload_small
    index_name = f"test-index-{str(uuid.uuid4())}"
    request_data = {
        "storage_name": blob_container_name,
        "index_name": index_name,
    }
    response = client.post(url=f"{client.base_url}{index_endpoint}", json=request_data)
    yield (index_name, response)  # test runs here


def test_index_create(client, index_create):
    index_name, response = index_create
    assert response.status_code == 200
    response = client.delete(url=f"{client.base_url}{index_endpoint}/{index_name}")


@pytest.fixture
def run_indexing(client, index_create):
    index_name, response_index = index_create
    print(f"Testing the building of index: {index_name}")
    while True:
        response = client.get(
            url=f"{client.base_url}{index_endpoint}/status/{index_name}"
        )
        assert response.status_code == 200
        percent_complete = response.json().get("percent_complete", None)
        status = response.json().get("status", None)
        print(f"Percent Complete: {percent_complete}")
        print(f"Status: {status}")
        if status == "failed":
            yield (False, index_name)
            break
        if status == "complete":
            print("Indexing Test Passed!")
            # assert True
            yield (True, index_name)
            break
        time.sleep(10)


def test_indexing_end_to_end(client, run_indexing):
    passed, index_name = run_indexing
    assert passed

    query_endpoint = "/query"
    graph_endpoint = "/graph"

    print(f"Got index name: {index_name}")

    request = {"index_name": index_name, "query": "Where is Alabama?"}
    global_response_new = client.post(
        f"{client.base_url}{query_endpoint}/global", json=request
    )
    assert global_response_new.status_code == 200
    print("Passed global search test.")

    global_response = global_response_new.json()
    if global_response["context_data"]["reports"] != []:
        report_id = global_response["context_data"]["reports"][0]["id"]
        response = client.get(
            f"{client.base_url}/source/report/{index_name}/{report_id}"
        )
        assert response.status_code == 200
        print("Passed /source - retrieving report id.")

    local_response = client.post(
        f"{client.base_url}{query_endpoint}/local", json=request
    )
    assert local_response.status_code == 200
    print("Passed local search test.")

    local_response = local_response.json()
    if local_response["context_data"]["entities"] != []:
        entity_id = local_response["context_data"]["entities"][0]["id"]
        entity_source_response = client.get(
            f"{client.base_url}/source/entity/{index_name}/{entity_id}"
        )
        assert entity_source_response.status_code == 200
        print("Passed /source - retrieving entity id.")

        text_unit_info = entity_source_response.json()
        first_unit = text_unit_info["text_units"][0]
        text_unit_source_response = client.get(
            f"{client.base_url}/source/text/{index_name}/{first_unit}"
        )
        assert text_unit_source_response.status_code == 200
        print("Passed /source - retrieving text unit.")

    if local_response["context_data"]["relationships"] != []:
        relationship_id = local_response["context_data"]["relationships"][0]["id"]
        relationship_response = client.get(
            f"{client.base_url}/source/relationship/{index_name}/{relationship_id}"
        )
        assert relationship_response.status_code == 200
        print("Passed /source - retrieving relationship.")

    response = client.get(f"{client.base_url}{graph_endpoint}/graphml/{index_name}")
    assert response.status_code == 200
    print("Passed retrieving graphml file.")

    response = client.get(f"{client.base_url}{graph_endpoint}/stats/{index_name}")
    assert response.status_code == 200
    print("Passed retrieving graph stats.")

    response = client.delete(url=f"{client.base_url}{index_endpoint}/{index_name}")
    assert response.status_code == 200
    print(f"Passed deleting index: {index_name}")
