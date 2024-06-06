# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import inspect
import json
import os
import traceback
from queue import Queue
from threading import Thread

import pandas as pd
import yaml
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from fastapi.responses import StreamingResponse
from graphrag.config import create_graphrag_config
from graphrag.query.llm.base import BaseLLMCallback
from graphrag.query.structured_search.global_search.callbacks import (
    GlobalSearchLLMCallback,
)

from src.api.common import (
    sanitize_name,
    validate_index_file_exist,
    verify_subscription_key_exist,
)
from src.api.query import _is_index_complete, _reformat_context_data
from src.meta_agent.global_search.retrieve import GlobalSearchHelpers
from src.models import GraphRequest
from src.utils import query as query_helper

experimental_route = APIRouter(
    prefix="/experimental",
    tags=["Experimental Operations"],
)
if os.getenv("KUBERNETES_SERVICE_HOST"):
    experimental_route.dependencies.append(Depends(verify_subscription_key_exist))


class GraphRagLLMCallback(GlobalSearchLLMCallback, BaseLLMCallback):
    """
    Contains functions to define custom callback handlers to enable the streaming of
    graphrag's response via a generator function.
    """

    def __init__(self, token_queue: Queue = None):
        super().__init__()
        self.q = token_queue

    def on_llm_new_token(self, token: str):
        self.q.put(
            json.dumps({"token": token, "context": None}).encode("utf-8"), block=True
        )


@experimental_route.post(
    "/query/global/streaming",
    summary="Stream a response back after performing a global search",
    description="Note: this is an experimental endpoint for testing and gathering initial feedback of interest. There is no quarantee of future support. The global query method generates answers by searching over all AI-generated community reports in a map-reduce fashion. This is a resource-intensive method, but often gives good responses for questions that require an understanding of the dataset as a whole.",
)
async def global_search_streaming(request: GraphRequest):
    # this is a slightly modified version of src.api.query.global_query() method
    if isinstance(request.index_name, str):
        index_names = [request.index_name]
    else:
        index_names = request.index_name
    sanitized_index_names = [sanitize_name(name) for name in index_names]

    for index_name in sanitized_index_names:
        if not _is_index_complete(index_name):
            raise HTTPException(
                status_code=500,
                detail=f"{index_name} not ready for querying.",
            )

    ENTITY_TABLE = "output/create_final_nodes.parquet"
    COMMUNITY_REPORT_TABLE = "output/create_final_community_reports.parquet"

    for index_name in sanitized_index_names:
        validate_index_file_exist(index_name, COMMUNITY_REPORT_TABLE)
        validate_index_file_exist(index_name, ENTITY_TABLE)

    # current investigations show that community level 1 is the most useful for global search
    COMMUNITY_LEVEL = 1
    try:
        report_dfs = []
        for index_name in sanitized_index_names:
            entity_table_path = f"abfs://{index_name}/{ENTITY_TABLE}"
            community_report_table_path = (
                f"abfs://{index_name}/{COMMUNITY_REPORT_TABLE}"
            )
            report_df = query_helper.get_reports(
                entity_table_path, community_report_table_path, COMMUNITY_LEVEL
            )
            report_dfs.append(report_df)

        # overload title field to include index_name and index_id for provenance tracking
        report_df = report_dfs[0]
        max_id = 0
        if len(report_df["community_id"]) > 0:
            max_id = report_df["community_id"].astype(int).max()
        report_df["title"] = [
            sanitized_index_names[0] + "<sep>" + i + "<sep>" + t
            for i, t in zip(report_df["community_id"], report_df["title"])
        ]
        for idx, df in enumerate(report_dfs[1:]):
            df["title"] = [
                sanitized_index_names[idx + 1] + "<sep>" + i + "<sep>" + t
                for i, t in zip(df["community_id"], df["title"])
            ]
            df["community_id"] = [str(int(i) + max_id + 1) for i in df["community_id"]]
            report_df = pd.concat([report_df, df], ignore_index=True, sort=False)
            if len(report_df["community_id"]) > 0:
                max_id = report_df["community_id"].astype(int).max()

        def stream_response(report_df, query, end_callback=(lambda x: x), timeout=300):
            """
            Stream a response back after performing a global search.

            Note: the graphrag package does not expose a streaming API at this time, so we devise
            a generator algorithm to stream the response by using a callback function that first inserts token
            responses from graphrag into a queue, and then blocks until the token
            is consumed by the generator.
            """
            q = Queue()
            callback = GraphRagLLMCallback(token_queue=q)
            # load custom pipeline settings
            this_directory = os.path.dirname(
                os.path.abspath(inspect.getfile(inspect.currentframe()))
            )
            data = yaml.safe_load(open(f"{this_directory}/pipeline_settings.yaml"))
            # layer the custom settings on top of the default configuration settings of graphrag
            parameters = create_graphrag_config(data, ".")

            global_search = GlobalSearchHelpers(config=parameters)
            search_engine = global_search.get_search_engine(
                report_df=report_df, callbacks=[callback]
            )
            job_done = object()  # signals the processing is done

            def task():
                # execute the search - this will block until the search is complete
                result = search_engine.search(query=query)
                # reformat context data to comply with our json schema
                result.context_data = _reformat_context_data(result.context_data)
                # emit EOM token to signal the end of the LLM response
                q.put(
                    json.dumps({"token": "<EOM>", "context": None}).encode("utf-8"),
                    block=True,
                )
                # after search is complete, stream back the context data
                for report in result.context_data["reports"]:
                    # map title into index_name, index_id and title for provenance tracking
                    context = dict(
                        {k: report[k] for k in report},
                        **{
                            "index_name": report["title"].split("<sep>")[0],
                            "index_id": report["title"].split("<sep>")[1],
                            "title": report["title"].split("<sep>")[2],
                        },
                    )
                    # update the context data in the callback object
                    q.put(
                        json.dumps({"token": "<EOM>", "context": context}).encode(
                            "utf-8"
                        ),
                        block=True,
                    )
                # emit stop signal
                q.put(
                    job_done, block=True
                )  # blocks until the token is consumed by the generator

            # start task in a new thread
            Thread(target=task).start()
            while True:
                next_item = q.get(
                    block=True, timeout=timeout
                )  # blocks until an input is available
                if next_item is job_done:
                    break
                # using b"\n" this will help us work around APIM max file size
                yield next_item + b"\n"

        return StreamingResponse(
            stream_response(report_df=report_df, query=request.query),
            media_type="application/json",
        )
    except Exception as e:
        # temporary logging of errors until reporters are in place
        print(e)
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
