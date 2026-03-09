"""Validation for parsed DSL graphs."""

from __future__ import annotations

from node_to_text.models import GraphDefinition, ValidationError
from node_to_text.schema.node_schema import resolve_tree_schema


class GraphValidationError(ValueError):
    """Raised when a graph is invalid for a target node tree."""

    def __init__(self, errors: list[ValidationError]):
        self.errors = errors
        super().__init__("\n".join(str(error) for error in errors))


def validate_graph(graph_def: GraphDefinition, node_tree_type, tree_schema=None) -> list[ValidationError]:
    schema = resolve_tree_schema(node_tree_type, tree_schema=tree_schema)
    live_inputs_by_id, live_outputs_by_id = _collect_live_sockets_by_node_id(node_tree_type)
    errors: list[ValidationError] = []
    seen_ids: set[str] = set()

    for node in graph_def.nodes:
        if node.id in seen_ids:
            errors.append(
                ValidationError(node.line_number, "DuplicateNodeId", f"Node id {node.id!r} is duplicated.")
            )
            continue
        seen_ids.add(node.id)

        node_schema = schema.node_types.get(node.type)
        if node_schema is None:
            errors.append(
                ValidationError(node.line_number, "UnknownNodeType", f"Unknown node type {node.type!r}.")
            )
            continue

        for property_name, property_value in node.properties.items():
            property_schema = node_schema.properties.get(property_name)
            valid_inputs = set(node_schema.inputs)
            valid_inputs.update(live_inputs_by_id.get(node.id, ()))
            if property_schema is None and property_name in valid_inputs:
                continue
            if property_schema is None:
                errors.append(
                    ValidationError(
                        node.line_number,
                        "UnknownProperty",
                        f"Unknown property {property_name!r} on node type {node.type}.",
                    )
                )
                continue
            if property_schema.enum_values and property_value not in property_schema.enum_values:
                errors.append(
                    ValidationError(
                        node.line_number,
                        "InvalidEnumValue",
                        f"Invalid value {property_value!r} for property {property_name!r}.",
                    )
                )

    nodes_by_id = graph_def.node_map()
    for edge in graph_def.edges:
        from_node = nodes_by_id.get(edge.from_node)
        to_node = nodes_by_id.get(edge.to_node)

        if from_node is None:
            errors.append(
                ValidationError(edge.line_number, "UnknownNodeId", f"Unknown source node {edge.from_node!r}.")
            )
            continue
        if to_node is None:
            errors.append(
                ValidationError(edge.line_number, "UnknownNodeId", f"Unknown target node {edge.to_node!r}.")
            )
            continue

        from_schema = schema.node_types.get(from_node.type)
        to_schema = schema.node_types.get(to_node.type)
        if from_schema is None or to_schema is None:
            continue

        valid_outputs = set(from_schema.outputs)
        valid_outputs.update(live_outputs_by_id.get(from_node.id, ()))
        valid_inputs = set(to_schema.inputs)
        valid_inputs.update(live_inputs_by_id.get(to_node.id, ()))

        if edge.from_socket not in valid_outputs:
            errors.append(
                ValidationError(
                    edge.line_number,
                    "UnknownSocket",
                    f"Unknown output socket {edge.from_socket!r} on node {edge.from_node}.",
                )
            )
        if edge.to_socket not in valid_inputs:
            errors.append(
                ValidationError(
                    edge.line_number,
                    "UnknownSocket",
                    f"Unknown input socket {edge.to_socket!r} on node {edge.to_node}.",
                )
            )

    return errors


def raise_for_errors(errors: list[ValidationError]) -> None:
    if errors:
        raise GraphValidationError(errors)


def _collect_live_sockets_by_node_id(node_tree) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    if not hasattr(node_tree, "nodes"):
        return {}, {}

    inputs_by_id: dict[str, set[str]] = {}
    outputs_by_id: dict[str, set[str]] = {}
    for node in getattr(node_tree, "nodes", []):
        node_id = getattr(node, "name", None)
        if not node_id:
            continue
        inputs_by_id[node_id] = {socket.name for socket in getattr(node, "inputs", [])}
        outputs_by_id[node_id] = {socket.name for socket in getattr(node, "outputs", [])}
    return inputs_by_id, outputs_by_id
