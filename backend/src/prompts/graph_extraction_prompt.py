# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import List

from src.models import EntityTypeExample

NEWLINE = "\n"


def _get_example(entity_examples: EntityTypeExample, last: bool = False) -> str:
    return f"""Entity_types: {entity_examples.entity_types}
    Text:
    {entity_examples.text}
    ######################
    Output:
    {entity_examples.output + (f"{NEWLINE}######################{NEWLINE}" if not last else "")}"""


def get_prompt(
    entity_types: List[str], entity_examples: List[EntityTypeExample]
) -> str:
    if len(entity_types) < 1:
        raise ValueError("entity_types cannot be empty")

    if len(entity_examples) < 1:
        raise ValueError("entity_examples cannot be empty")

    # define the extraction goal
    GRAPH_EXTRACTION_PROMPT = (
        """
    -Goal-
    Given a text document that is potentially relevant to this activity and a list of entity types, identify all entities of those types from the text and all relationships among the identified entities.

    -Steps-
    1. Identify all entities. For each identified entity, extract the following information:
    - entity_name: Name of the entity, capitalized
    - entity_type: One of the following types: [{entity_types}]
    - entity_description: Comprehensive description of the entity's attributes and activities
    Format each entity as ("entity"{tuple_delimiter}<entity_name>{tuple_delimiter}<entity_type>{tuple_delimiter}<entity_description>)

    2. From the entities identified in step 1, identify all pairs of (source_entity, target_entity) that are *clearly related* to each other.
    For each pair of related entities, extract the following information:
    - source_entity: name of the source entity, as identified in step 1
    - target_entity: name of the target entity, as identified in step 1
    - relationship_description: explanation as to why you think the source entity and the target entity are related to each other
    - relationship_strength: a numeric score indicating strength of the relationship between the source entity and target entity
    Format each relationship as ("relationship"{tuple_delimiter}<source_entity>{tuple_delimiter}<target_entity>{tuple_delimiter}<relationship_description>{tuple_delimiter}<relationship_strength>)

    3. Return output in English as a single list of all the entities and relationships identified in steps 1 and 2. Use **{record_delimiter}** as the list delimiter.

    4. When finished, output {completion_delimiter}

    ######################
    -Examples-
    ######################
    {examples}
    ######################
    -Real Data-
    ######################
    Entity_types: {entity_types}
    Text: {input_text}
    ######################
    Output:
    """
        # define the entity types to be extracted
        .replace("{entity_types}", ",".join(entity_types))
        # define the extraction examples
        .replace(
            "{examples}",
            "".join(
                [
                    _get_example(entity_example, i == len(entity_examples))
                    for i, entity_example in enumerate(entity_examples, start=1)
                ]
            ),
        )
        # eliminate leading white spaces (lstrip is not working)
        .replace("    ", "")  # replace white 4 spaces with 1 space
    )
    return GRAPH_EXTRACTION_PROMPT
