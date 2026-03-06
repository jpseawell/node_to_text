"""Helpers for Blender node trees and graph extraction."""

from __future__ import annotations

from node_to_text.models import EdgeDef, GraphDefinition, NodeDef, PrimitiveValue
from node_to_text.schema.node_schema import SUPPORTED_TREE_TYPES, resolve_tree_schema


def get_active_node_tree(context):
    space_data = getattr(context, "space_data", None)
    if space_data is None or getattr(space_data, "type", None) != "NODE_EDITOR":
        raise ValueError("Open a Node Editor to use Node to Text.")
    node_tree = getattr(space_data, "edit_tree", None) or getattr(space_data, "node_tree", None)
    if node_tree is None:
        raise ValueError("The active Node Editor does not have a node tree.")
    if getattr(node_tree, "bl_idname", None) not in SUPPORTED_TREE_TYPES:
        raise ValueError("Only Shader, Geometry, and Compositor node trees are supported.")
    return node_tree


def graph_from_node_tree(node_tree, tree_schema=None) -> GraphDefinition:
    schema = resolve_tree_schema(node_tree, tree_schema=tree_schema)
    nodes: list[NodeDef] = []
    edges: list[EdgeDef] = []

    for node in getattr(node_tree, "nodes", []):
        node_schema = schema.node_types.get(node.bl_idname)
        properties = extract_exportable_properties(node, node_schema)
        nodes.append(NodeDef(id=node.name, type=node.bl_idname, properties=properties))

    for link in getattr(node_tree, "links", []):
        if not getattr(link, "is_valid", True):
            continue
        edges.append(
            EdgeDef(
                from_node=link.from_node.name,
                from_socket=link.from_socket.name,
                to_node=link.to_node.name,
                to_socket=link.to_socket.name,
            )
        )

    return GraphDefinition(nodes=nodes, edges=edges)


def extract_exportable_properties(node, node_schema=None) -> dict[str, PrimitiveValue]:
    if node_schema is None:
        return {}

    properties: dict[str, PrimitiveValue] = {}
    for property_name, property_schema in sorted(node_schema.properties.items()):
        value = normalize_property_value(getattr(node, property_name, None))
        if value != property_schema.default:
            properties[property_name] = value

    for socket in getattr(node, "inputs", []):
        if getattr(socket, "is_linked", False) or not hasattr(socket, "default_value"):
            continue
        value = normalize_property_value(socket.default_value)
        if value is not None:
            properties[socket.name] = value
    return properties


def normalize_property_value(value) -> PrimitiveValue:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, (tuple, list)):
        normalized = [normalize_property_value(item) for item in value]
        if any(item is None for item in normalized):
            return None
        return tuple(normalized)
    if value is None:
        return None
    if hasattr(value, "__iter__") and not isinstance(value, (bytes, bytearray, dict)):
        normalized = [normalize_property_value(item) for item in value]
        if normalized and not any(item is None for item in normalized):
            return tuple(normalized)
    return None


def find_node(node_tree, node_id: str):
    return getattr(node_tree.nodes, "get", lambda _: None)(node_id)


def get_socket(node, socket_name: str, is_output: bool):
    sockets = node.outputs if is_output else node.inputs
    socket = sockets.get(socket_name) if hasattr(sockets, "get") else None
    if socket is not None:
        return socket
    for candidate in sockets:
        if candidate.name == socket_name:
            return candidate
    raise ValueError(f"Socket {socket_name!r} was not found on node {node.name}.")
