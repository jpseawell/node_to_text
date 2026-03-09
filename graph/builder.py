"""Apply validated graph definitions to Blender node trees."""

from __future__ import annotations

from node_to_text.graph.diff_engine import compute_diff
from node_to_text.graph.node_utils import find_node, get_socket, graph_from_node_tree
from node_to_text.models import GraphDefinition, GraphDiff
from node_to_text.schema.node_schema import resolve_tree_schema


def apply_graph(graph_def: GraphDefinition, node_tree, tree_schema=None) -> GraphDiff:
    schema = resolve_tree_schema(node_tree, tree_schema=tree_schema)
    existing_graph = graph_from_node_tree(node_tree, tree_schema=schema)
    diff = compute_diff(existing_graph, graph_def)
    apply_diff(diff, node_tree, schema)
    return diff


def apply_diff(diff: GraphDiff, node_tree, tree_schema) -> None:
    for edge in diff.links_to_remove:
        _remove_link(node_tree, edge)

    for node_id in diff.nodes_to_remove:
        node = find_node(node_tree, node_id)
        if node is not None:
            node_tree.nodes.remove(node)

    for node_def in diff.nodes_to_add:
        node = node_tree.nodes.new(node_def.type)
        node.name = node_def.id
        for property_name, value in sorted(node_def.properties.items()):
            _apply_assignment(node, property_name, value)

    for change in diff.property_changes:
        node = find_node(node_tree, change.node_id)
        if node is None:
            raise ValueError(f"Node {change.node_id!r} is missing during graph apply.")
        node_schema = tree_schema.node_types[node.bl_idname]
        property_schema = node_schema.properties.get(change.property_name)
        if property_schema is not None:
            value = property_schema.default if change.clear else change.value
            _apply_assignment(node, change.property_name, value)
            continue
        if change.property_name in node_schema.inputs or _has_input_socket(node, change.property_name):
            socket = get_socket(node, change.property_name, is_output=False)
            if not hasattr(socket, "default_value"):
                raise ValueError(
                    f"Input socket {change.property_name!r} on node type {node.bl_idname} does not support default values."
                )
            if change.clear:
                continue
            socket.default_value = change.value
            continue
        raise ValueError(
            f"Property {change.property_name!r} is not valid on node type {node.bl_idname}."
        )

    for edge in diff.links_to_add:
        from_node = find_node(node_tree, edge.from_node)
        to_node = find_node(node_tree, edge.to_node)
        if from_node is None or to_node is None:
            raise ValueError("Cannot create a link for a node that does not exist.")
        output_socket = get_socket(from_node, edge.from_socket, is_output=True)
        input_socket = get_socket(to_node, edge.to_socket, is_output=False)
        node_tree.links.new(output_socket, input_socket)


def _remove_link(node_tree, edge) -> None:
    for link in list(node_tree.links):
        if (
            link.from_node.name == edge.from_node
            and link.from_socket.name == edge.from_socket
            and link.to_node.name == edge.to_node
            and link.to_socket.name == edge.to_socket
        ):
            node_tree.links.remove(link)


def _apply_assignment(node, assignment_name, value) -> None:
    if hasattr(node, assignment_name):
        setattr(node, assignment_name, value)
        return
    socket = get_socket(node, assignment_name, is_output=False)
    if not hasattr(socket, "default_value"):
        raise ValueError(
            f"Input socket {assignment_name!r} on node type {node.bl_idname} does not support default values."
        )
    socket.default_value = value


def _has_input_socket(node, socket_name: str) -> bool:
    sockets = getattr(node, "inputs", [])
    if hasattr(sockets, "get") and sockets.get(socket_name) is not None:
        return True
    return any(getattr(socket, "name", None) == socket_name for socket in sockets)
