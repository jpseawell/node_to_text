"""Schema text generation for LLM guidance."""

from __future__ import annotations

from node_to_text.schema.node_schema import resolve_tree_schema


def generate_schema(node_tree_type, tree_schema=None, included_node_types=None) -> str:
    schema = resolve_tree_schema(node_tree_type, tree_schema=tree_schema)
    allowed_types = _normalize_included_types(schema, included_node_types)
    lines: list[str] = []
    for node_type in sorted(allowed_types):
        node_schema = schema.node_types[node_type]
        inputs = ", ".join(node_schema.inputs) or "-"
        outputs = ", ".join(node_schema.outputs) or "-"
        lines.append(f"{node_type}")
        lines.append(f"  inputs: {inputs}")
        lines.append(f"  outputs: {outputs}")
        if node_schema.properties:
            lines.append(f"  properties: {', '.join(sorted(node_schema.properties))}")
    return "\n".join(lines)


def generate_relevant_schema(node_tree, tree_schema=None) -> str:
    schema = resolve_tree_schema(node_tree, tree_schema=tree_schema)
    included_node_types = {node.bl_idname for node in getattr(node_tree, "nodes", [])}
    return generate_schema(schema, included_node_types=included_node_types)


def _normalize_included_types(schema, included_node_types) -> set[str]:
    if included_node_types is None:
        return set(schema.node_types)
    return {node_type for node_type in included_node_types if node_type in schema.node_types}
