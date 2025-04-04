# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from dataclasses import dataclass, field
from time import time
from typing import (
    List,
)

from azure.cosmos.exceptions import CosmosHttpResponseError
from graphrag.config.enums import IndexingMethod

from graphrag_app.typing.pipeline import PipelineJobState
from graphrag_app.utils.azure_clients import AzureClientManager
from graphrag_app.utils.common import sanitize_name


@dataclass
class PipelineJob:
    """Indexing Pipeline Job metadata

    This is a custom class where the attributes are stored/retrieved in cosmosdb.
    # TODO: fix the class so initiliazation is not required
    """

    _id: str = field(default=None, init=False)
    _epoch_request_time: int = field(default=None, init=False)
    _index_name: str = field(default=None, init=False)
    _human_readable_index_name: str = field(default=None, init=False)
    _sanitized_index_name: str = field(default=None, init=False)
    _human_readable_storage_name: str = field(default=None, init=False)
    _sanitized_storage_name: str = field(default=None, init=False)

    _all_workflows: List[str] = field(default_factory=list, init=False)
    _completed_workflows: List[str] = field(default_factory=list, init=False)
    _failed_workflows: List[str] = field(default_factory=list, init=False)

    _status: PipelineJobState = field(default=None, init=False)
    _percent_complete: float = field(default=0, init=False)
    _progress: str = field(default="", init=False)

    _entity_extraction_prompt: str = field(default=None, init=False)
    _entity_summarization_prompt: str = field(default=None, init=False)
    _community_summarization_graph_prompt: str = field(default=None, init=False)
    _community_summarization_text_prompt: str = field(default=None, init=False)
    _indexing_method: str = field(default=IndexingMethod.Standard.value, init=False)

    @staticmethod
    def _jobs_container():
        azure_storage_client = AzureClientManager()
        return azure_storage_client.get_cosmos_container_client(
            database="graphrag", container="jobs"
        )

    @classmethod
    def create_item(
        cls,
        id: str,
        human_readable_index_name: str,
        human_readable_storage_name: str,
        entity_extraction_prompt: str | None = None,
        entity_summarization_prompt: str | None = None,
        community_summarization_graph_prompt: str | None = None,
        community_summarization_text_prompt: str | None = None,
        indexing_method: str = IndexingMethod.Standard.value,
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
        assert human_readable_index_name is not None, "index_name cannot be None."
        assert len(human_readable_index_name) > 0, "index_name cannot be empty."
        assert human_readable_storage_name is not None, "storage_name cannot be None."
        assert len(human_readable_storage_name) > 0, "storage_name cannot be empty."

        instance = cls.__new__(
            cls, id, human_readable_index_name, human_readable_storage_name, **kwargs
        )
        instance._id = id
        instance._epoch_request_time = int(time())
        instance._human_readable_index_name = human_readable_index_name
        instance._sanitized_index_name = sanitize_name(human_readable_index_name)
        instance._human_readable_storage_name = human_readable_storage_name
        instance._sanitized_storage_name = sanitize_name(human_readable_storage_name)

        instance._all_workflows = kwargs.get("all_workflows", [])
        instance._completed_workflows = kwargs.get("completed_workflows", [])
        instance._failed_workflows = kwargs.get("failed_workflows", [])

        instance._status = PipelineJobState(
            kwargs.get("status", PipelineJobState.SCHEDULED.value)
        )
        instance._percent_complete = kwargs.get("percent_complete", 0.0)
        instance._progress = kwargs.get("progress", "")

        instance._entity_extraction_prompt = entity_extraction_prompt
        instance._entity_summarization_prompt = entity_summarization_prompt
        instance._community_summarization_graph_prompt = community_summarization_graph_prompt
        instance._community_summarization_text_prompt = community_summarization_text_prompt

        instance._indexing_method = IndexingMethod(indexing_method).value

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
        instance._epoch_request_time = db_item.get("epoch_request_time")
        instance._index_name = db_item.get("index_name")
        instance._human_readable_index_name = db_item.get("human_readable_index_name")
        instance._sanitized_index_name = db_item.get("sanitized_index_name")
        instance._human_readable_storage_name = db_item.get(
            "human_readable_storage_name"
        )
        instance._sanitized_storage_name = db_item.get("sanitized_storage_name")

        instance._all_workflows = db_item.get("all_workflows", [])
        instance._completed_workflows = db_item.get("completed_workflows", [])
        instance._failed_workflows = db_item.get("failed_workflows", [])

        instance._status = PipelineJobState(db_item.get("status"))
        instance._percent_complete = db_item.get("percent_complete", 0.0)
        instance._progress = db_item.get("progress", "")

        instance._entity_extraction_prompt = db_item.get("entity_extraction_prompt")
        instance._entity_summarization_prompt = db_item.get(
            "entity_summarization_prompt"
        )
        instance._community_summarization_graph_prompt = db_item.get(
            "community_summarization_graph_prompt"
        )
        instance._community_summarization_text_prompt = db_item.get(
            "community_summarization_text_prompt"
        )

        instance._indexing_method = db_item.get("indexing_method")

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
            "epoch_request_time": self._epoch_request_time,
            "human_readable_index_name": self._human_readable_index_name,
            "sanitized_index_name": self._sanitized_index_name,
            "human_readable_storage_name": self._human_readable_storage_name,
            "sanitized_storage_name": self._sanitized_storage_name,
            "all_workflows": self._all_workflows,
            "completed_workflows": self._completed_workflows,
            "failed_workflows": self._failed_workflows,
            "status": self._status.value,
            "percent_complete": self._percent_complete,
            "progress": self._progress,
            "indexing_method": self._indexing_method,
        }
        if self._entity_extraction_prompt:
            model["entity_extraction_prompt"] = self._entity_extraction_prompt
        if self._entity_summarization_prompt:
            model["entity_summarization_prompt"] = self._entity_summarization_prompt
        if self._community_summarization_graph_prompt:
            model["community_summarization_graph_prompt"] = (
                self._community_summarization_graph_prompt
            )
        if self._community_summarization_text_prompt:
            model["community_summarization_text_prompt"] = (
                self._community_summarization_text_prompt
            )
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
    def epoch_request_time(self) -> int:
        return self._epoch_request_time

    @epoch_request_time.setter
    def epoch_request_time(self, epoch_request_time: int) -> None:
        if self._epoch_request_time is not None:
            self._epoch_request_time = epoch_request_time
        else:
            raise ValueError("ID cannot be changed once set.")

    @property
    def human_readable_index_name(self) -> str:
        return self._human_readable_index_name

    @human_readable_index_name.setter
    def human_readable_index_name(self, human_readable_index_name: str) -> None:
        self._human_readable_index_name = human_readable_index_name
        self.update_db()

    @property
    def sanitized_index_name(self) -> str:
        return self._sanitized_index_name

    @sanitized_index_name.setter
    def sanitized_index_name(self, sanitized_index_name: str) -> None:
        self._sanitized_index_name = sanitized_index_name
        self.update_db()

    @property
    def human_readable_storage_name(self) -> str:
        return self._human_readable_storage_name

    @human_readable_storage_name.setter
    def human_readable_storage_name(self, human_readable_storage_name: str) -> None:
        self._human_readable_storage_name = human_readable_storage_name
        self.update_db()

    @property
    def sanitized_storage_name(self) -> str:
        return self._sanitized_storage_name

    @sanitized_storage_name.setter
    def sanitized_storage_name(self, sanitized_storage_name: str) -> None:
        self._sanitized_storage_name = sanitized_storage_name
        self.update_db()

    @property
    def entity_extraction_prompt(self) -> str:
        return self._entity_extraction_prompt

    @entity_extraction_prompt.setter
    def entity_extraction_prompt(self, entity_extraction_prompt: str) -> None:
        self._entity_extraction_prompt = entity_extraction_prompt
        self.update_db()

    @property
    def entity_summarization_prompt(self) -> str:
        return self._entity_summarization_prompt

    @entity_summarization_prompt.setter
    def entity_summarization_prompt(self, entity_summarization_prompt: str) -> None:
        self._entity_summarization_prompt = entity_summarization_prompt
        self.update_db()

    @property
    def community_summarization_graph_prompt(self) -> str:
        return self._community_summarization_graph_prompt

    @community_summarization_graph_prompt.setter
    def community_summarization_graph_prompt(
        self, community_summarization_graph_prompt: str
    ) -> None:
        self._community_summarization_graph_prompt = community_summarization_graph_prompt
        self.update_db()
    
    @property
    def community_summarization_text_prompt(self) -> str:
        return self._community_summarization_text_prompt

    @community_summarization_text_prompt.setter
    def community_summarization_text_prompt(
        self, community_summarization_text_prompt: str
    ) -> None:
        self._community_summarization_text_prompt = community_summarization_text_prompt
        self.update_db()

    @property
    def indexing_method(self) -> str:
        return self._indexing_method
    
    @indexing_method.setter
    def indexing_method(self, indexing_method: str) -> None:
        self._indexing_method = IndexingMethod(indexing_method).value
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
