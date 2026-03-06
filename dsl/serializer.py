"""Serializer for Blender node graphs and graph definitions."""

from __future__ import annotations

import json
import re

from node_to_text.graph.node_utils import graph_from_node_tree
from node_to_text.models import GraphDefinition, PrimitiveValue

_BARE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.:+-]+$")


def export_node_tree(node_tree, tree_schema=None) -> str:
    graph = graph_from_node_tree(node_tree, tree_schema=tree_schema)
    return serialize_graph(graph)


def serialize_graph(graph: GraphDefinition) -> str:
    lines: list[str] = []

    for node in sorted(graph.nodes, key=lambda item: item.id):
        parts = ["node", format_identifier(node.id), node.type]
        for key, value in sorted(node.properties.items()):
            parts.append(f"{key}={format_value(value)}")
        lines.append(" ".join(parts))

    for edge in sorted(graph.edges, key=lambda item: item.key()):
        lines.append(
            f"connect {format_identifier(edge.from_node)}.{edge.from_socket} -> {format_identifier(edge.to_node)}.{edge.to_socket}"
        )

    return "\n".join(lines)


def format_identifier(value: str) -> str:
    if _BARE_TOKEN_RE.match(value):
        return value
    return json.dumps(value)


def format_value(value: PrimitiveValue) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (tuple, list)):
        return "(" + ",".join(format_value(item) for item in value) + ")"
    if _BARE_TOKEN_RE.match(value):
        return value
    return json.dumps(value)
