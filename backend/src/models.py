# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from dataclasses import dataclass, field
from typing import (
    Any,
    List,
)

from azure.cosmos.exceptions import CosmosHttpResponseError
from pydantic import BaseModel

from src.api.azure_clients import AzureStorageClientManager
from src.typing import PipelineJobState


class BaseResponse(BaseModel):
    status: str


class ClaimResponse(BaseModel):
    covariate_type: str
    type: str
    description: str
    subject_id: str
    object_id: str
    source_text: str
    text_unit_id: str
    document_ids: List[str]


class EntityNameList(BaseModel):
    entity_configuration_name: List[str]


class EntityResponse(BaseModel):
    name: str
    description: str
    text_units: list[str]


class EntityTypeExample(BaseModel):
    entity_types: str
    text: str
    output: str


class EntityConfiguration(BaseModel):
    entity_configuration_name: str
    entity_types: List[str]
    entity_examples: List[EntityTypeExample]


class GraphRequest(BaseModel):
    index_name: str | List[str]
    query: str


class GraphResponse(BaseModel):
    result: Any
    context_data: Any


class GraphDataResponse(BaseModel):
    nodes: int
    edges: int


class IndexNameList(BaseModel):
    index_name: List[str]


class IndexStatusResponse(BaseModel):
    status_code: int
    index_name: str
    storage_name: str
    status: str
    percent_complete: float
    progress: str


class ReportResponse(BaseModel):
    text: str


class RelationshipResponse(BaseModel):
    source: str
    source_id: int
    target: str
    target_id: int
    description: str
    text_units: list[str]


class StorageNameList(BaseModel):
    storage_name: List[str]


class TextUnitResponse(BaseModel):
    text: str
    source_document: str


@dataclass
class PipelineJob:
    _id: str = field(default=None, init=False)
    _index_name: str = field(default=None, init=False)
    _storage_name: str = field(default=None, init=False)
    _entity_extraction_prompt: str = field(default=None, init=False)
    _community_report_prompt: str = field(default=None, init=False)
    _summarize_descriptions_prompt: str = field(default=None, init=False)
    _all_workflows: List[str] = field(default_factory=list, init=False)
    _completed_workflows: List[str] = field(default_factory=list, init=False)
    _failed_workflows: List[str] = field(default_factory=list, init=False)
    _status: PipelineJobState = field(default=None, init=False)
    _percent_complete: float = field(default=0, init=False)
    _progress: str = field(default="", init=False)

    @staticmethod
    def _jobs_container():
        azure_storage_client = AzureStorageClientManager()
        return azure_storage_client.get_cosmos_container_client(
            database_name="graphrag", container_name="jobs"
        )

    @classmethod
    def create_item(
        cls,
        id: str,
        index_name: str,
        storage_name: str,
        entity_extraction_prompt: str | None = None,
        community_report_prompt: str | None = None,
        summarize_descriptions_prompt: str | None = None,
        **kwargs,
    ) -> "PipelineJob":
        """
        This method creates a new instance of the PipelineJob class and adds it to the database.

        Args:
            id (str): The ID of the pipeline job.
            index_name (str): The name of the index.
            storage_name (str): The name of the storage.
            entity_extraction_prompt (str): The entity extraction prompt.
            community_prompt (str): The community prompt.
            summarize_descriptions_prompt (str): The prompt for summarizing descriptions.
            all_workflows (List[str]): List of all workflows.
            completed_workflows (List[str]): List of completed workflows.
            failed_workflows (List[str]): List of failed workflows.
            status (PipelineJobState): The status of the pipeline job.
            percent_complete (float): The percentage of completion.
            progress (str): The progress of the pipeline job.
        Returns:
            PipelineJob: The created pipeline job instance.
        """
        if PipelineJob.item_exist(id):
            raise ValueError(
                f"Pipeline job with ID {id} already exist. "
                "Use PipelineJob.load_item() to create a new pipeline job."
            )

        assert id is not None, "ID cannot be None."
        assert index_name is not None, "index_name cannot be None."
        assert len(index_name) > 0, "index_name cannot be empty."
        assert storage_name is not None, "storage_name cannot be None."
        assert len(storage_name) > 0, "storage_name cannot be empty."

        instance = cls.__new__(cls, id, index_name, storage_name, **kwargs)
        instance._id = id
        instance._index_name = index_name
        instance._storage_name = storage_name
        instance._entity_extraction_prompt = entity_extraction_prompt
        instance._community_report_prompt = community_report_prompt
        instance._summarize_descriptions_prompt = summarize_descriptions_prompt
        instance._all_workflows = kwargs.get("all_workflows", [])
        instance._completed_workflows = kwargs.get("completed_workflows", [])
        instance._failed_workflows = kwargs.get("failed_workflows", [])
        instance._status = PipelineJobState(
            kwargs.get("status", PipelineJobState.SCHEDULED.value)
        )
        instance._percent_complete = kwargs.get("percent_complete", 0.0)
        instance._progress = kwargs.get("progress", "")

        # Create the item in the database
        instance.update_db()
        return instance

    @classmethod
    def load_item(cls, id: str) -> "PipelineJob":
        """
        This method loads an existing pipeline job from the database and returns
        it as an instance of the PipelineJob class.

        Args:
            id (str): The ID of the pipeline job.

        Returns:
            PipelineJob: The loaded pipeline job instance.
        """
        try:
            db_item = PipelineJob._jobs_container().read_item(item=id, partition_key=id)
        except CosmosHttpResponseError:
            raise ValueError(
                f"Pipeline job with ID {id} does not exist. "
                "Use PipelineJob.create_item() to create a new pipeline job."
            )
        instance = cls.__new__(cls, **db_item)
        instance._id = db_item.get("id")
        instance._index_name = db_item.get("index_name")
        instance._storage_name = db_item.get("storage_name")
        instance._entity_extraction_prompt = db_item.get("entity_extraction_prompt")
        instance._community_report_prompt = db_item.get("community_report_prompt")
        instance._summarize_descriptions_prompt = db_item.get(
            "summarize_descriptions_prompt"
        )
        instance._all_workflows = db_item.get("all_workflows", [])
        instance._completed_workflows = db_item.get("completed_workflows", [])
        instance._failed_workflows = db_item.get("failed_workflows", [])
        instance._status = PipelineJobState(db_item.get("status"))
        instance._percent_complete = db_item.get("percent_complete", 0.0)
        instance._progress = db_item.get("progress", "")
        return instance

    @staticmethod
    def item_exist(id: str) -> bool:
        try:
            PipelineJob._jobs_container().read_item(item=id, partition_key=id)
            return True
        except CosmosHttpResponseError:
            return False

    def calculate_percent_complete(self) -> float:
        """
        This method calculates the percentage of completion of the pipeline job.

        Returns:
            float: The percentage of completion.
        """
        if len(self.completed_workflows) == 0 or len(self.all_workflows) == 0:
            return 0.0
        return round(
            (len(self.completed_workflows) / len(self.all_workflows)) * 100, ndigits=2
        )

    def dump_model(self) -> dict:
        model = {
            "id": self._id,
            "index_name": self._index_name,
            "storage_name": self._storage_name,
            "all_workflows": self._all_workflows,
            "completed_workflows": self._completed_workflows,
            "failed_workflows": self._failed_workflows,
            "status": self._status.value,
            "percent_complete": self._percent_complete,
            "progress": self._progress,
        }
        if self._entity_extraction_prompt:
            model["entity_extraction_prompt"] = self._entity_extraction_prompt
        if self._community_report_prompt:
            model["community_report_prompt"] = self._community_report_prompt
        if self._summarize_descriptions_prompt:
            model["summarize_descriptions_prompt"] = self._summarize_descriptions_prompt
        return model

    def update_db(self):
        PipelineJob._jobs_container().upsert_item(body=self.dump_model())

    @property
    def id(self) -> str:
        return self._id

    @id.setter
    def id(self, id: str) -> None:
        if self._id is not None:
            self._id = id
        else:
            raise ValueError("ID cannot be changed once set.")

    @property
    def index_name(self) -> str:
        return self._index_name

    @index_name.setter
    def index_name(self, index_name: str) -> None:
        self._index_name = index_name
        self.update_db()

    @property
    def storage_name(self) -> str:
        return self._storage_name

    @storage_name.setter
    def storage_name(self, storage_name: str) -> None:
        self._storage_name = storage_name
        self.update_db()

    @property
    def entity_extraction_prompt(self) -> str:
        return self._entity_extraction_prompt

    @entity_extraction_prompt.setter
    def entity_extraction_prompt(self, entity_extraction_prompt: str) -> None:
        self._entity_extraction_prompt = entity_extraction_prompt
        self.update_db()

    @property
    def community_report_prompt(self) -> str:
        return self._community_report_prompt

    @community_report_prompt.setter
    def community_report_prompt(self, community_report_prompt: str) -> None:
        self._community_report_prompt = community_report_prompt
        self.update_db()

    @property
    def summarize_descriptions_prompt(self) -> str:
        return self._summarize_descriptions_prompt

    @summarize_descriptions_prompt.setter
    def summarize_descriptions_prompt(self, summarize_descriptions_prompt: str) -> None:
        self._summarize_descriptions_prompt = summarize_descriptions_prompt
        self.update_db()

    @property
    def all_workflows(self) -> List[str]:
        return self._all_workflows

    @all_workflows.setter
    def all_workflows(self, all_workflows: List[str]) -> None:
        self._all_workflows = all_workflows
        self.update_db()

    @property
    def completed_workflows(self) -> List[str]:
        return self._completed_workflows

    @completed_workflows.setter
    def completed_workflows(self, completed_workflows: List[str]) -> None:
        self._completed_workflows = completed_workflows
        self.update_db()

    @property
    def failed_workflows(self) -> List[str]:
        return self._failed_workflows

    @failed_workflows.setter
    def failed_workflows(self, failed_workflows: List[str]) -> None:
        self._failed_workflows = failed_workflows
        self.update_db()

    @property
    def status(self) -> PipelineJobState:
        return self._status

    @status.setter
    def status(self, status: PipelineJobState) -> None:
        self._status = status
        self.update_db()

    @property
    def percent_complete(self) -> float:
        return self._percent_complete

    @percent_complete.setter
    def percent_complete(self, percent_complete: float) -> None:
        self._percent_complete = percent_complete
        self.update_db()

    @property
    def progress(self) -> str:
        return self._progress

    @progress.setter
    def progress(self, progress: str) -> None:
        self._progress = progress
        self.update_db()
