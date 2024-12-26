# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import io
from typing import cast

import networkx as nx
import pandas as pd
from datashaper import (
    NoopWorkflowCallbacks,
    WorkflowCallbacks,
)
from graphrag.index import PipelineStorage
from graphrag.index.emit import (
    TableEmitterType,
    create_table_emitters,
)

from src.logger.console_workflow_callbacks import ConsoleWorkflowCallbacks

workflows_to_concat = [
    "create_base_text_units",
    "create_base_documents",
    "create_final_covariates",
    "create_base_entity_nodes",
]

workflows_to_merge = ["create_base_extracted_entities", *workflows_to_concat]


def merge_nodes(target: nx.Graph, subgraph: nx.Graph):
    """Merge nodes from subgraph into target using the operations defined in node_ops."""
    for node in subgraph.nodes:
        if node not in target.nodes:
            target.add_node(node, **(subgraph.nodes[node] or {}))
        else:
            merge_attributes(target.nodes[node], subgraph.nodes[node])


def merge_edges(target_graph: nx.Graph, subgraph: nx.Graph):
    """Merge edges from subgraph into target using the operations defined in edge_ops."""
    for source, target, edge_data in subgraph.edges(data=True):  # type: ignore
        if not target_graph.has_edge(source, target):
            target_graph.add_edge(source, target, **(edge_data or {}))
        else:
            merge_attributes(target_graph.edges[(source, target)], edge_data)


def merge_attributes(target_item, source_item):
    separator = ","
    for attrib in ["source_id", "description"]:
        target_attrib = target_item.get(attrib, "") or ""
        source_attrib = source_item.get(attrib, "") or ""
        target_item[attrib] = f"{target_attrib}{separator}{source_attrib}"
        if attrib == "source_id":
            target_item[attrib] = separator.join(
                sorted(set(target_item[attrib].split(separator)))
            )


def merge_two_graphml_dataframes(df1, df2):
    mega_graph = nx.Graph()
    G1 = nx.read_graphml(io.BytesIO(df1["entity_graph"][0].encode()))
    G2 = nx.read_graphml(io.BytesIO(df2["entity_graph"][0].encode()))
    for graph in [G1, G2]:
        merge_nodes(mega_graph, graph)
        merge_edges(mega_graph, graph)
    return pd.DataFrame([{"entity_graph": "\n".join(nx.generate_graphml(mega_graph))}])


async def merge_with_graph(
    merge_with_index: str,
    workflow_name: str,
    workflow_index_name: str,
    workflow_df: pd.DataFrame,
    workflow_storage: PipelineStorage,
    merge_with_storage: PipelineStorage,
    reporter: NoopWorkflowCallbacks | None = None,
) -> pd.DataFrame:
    """Execute this callback when a workflow ends."""

    reporter = reporter or ConsoleWorkflowCallbacks()
    if workflow_name in workflows_to_merge:
        reporter.on_log(
            message=(
                f"Starting index merge process. Workflow name: {workflow_name}, "
                + f"Workflow index name: {workflow_index_name}, "
                + f"Existing Index Name: {merge_with_index}."
            )
        )

        # load existing index table
        data = await merge_with_storage.get(f"{workflow_name}.parquet", as_bytes=True)
        existing_df = pd.read_parquet(io.BytesIO(data))

        # validate data tables
        validate_data(workflow_name, workflow_df, existing_df)

        # merge the data tables
        if workflow_name in workflows_to_concat:
            workflow_df = pd.concat((existing_df, workflow_df), axis=0).reset_index(
                drop=True
            )

        # merge the data graphs
        if workflow_name in ["create_base_extracted_entities"]:
            workflow_df = merge_two_graphml_dataframes(existing_df, workflow_df)

        # create a Parquet emitter to save files to storage
        emitter = create_table_emitters(
            [TableEmitterType.Parquet],
            workflow_storage,
            lambda e, s, d: cast(WorkflowCallbacks, reporter).on_error(
                "Error emitting table", e, s, d
            ),
        ).pop()
        # overwrite the workflow data table
        await emitter.emit(workflow_name, workflow_df)

        # log merge process update
        reporter.on_log(
            message=(
                f"Completed index merge process. Workflow name: {workflow_name}, "
                + f"Workflow index name: {workflow_index_name}, "
                + f"Existing Index Name: {merge_with_index}."
            )
        )

        return workflow_df


def validate_data(
    workflow_name: str,
    workflow_df: pd.DataFrame,
    existing_df: pd.DataFrame,
    reporter: NoopWorkflowCallbacks | None = None,
):
    reporter = reporter or ConsoleWorkflowCallbacks()
    if workflow_df is None or workflow_df.empty:
        reporter.on_error(
            f"The {workflow_name} workflow did not produce any output.",
            cause="{name}.parquet table is None or empty.",
        )
        raise ValueError(f"The {workflow_name} workflow did not produce any output.")

    if existing_df is None or existing_df.empty:
        reporter.on_error(
            "The existing index has no data to merge with.",
            cause=f"{workflow_name}.parquet table is None or empty.",
        )
        raise ValueError(f"{workflow_name}.parquet has no data to merge with.")
