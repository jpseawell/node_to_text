"""Schema text generation for LLM guidance."""

from __future__ import annotations

from node_to_text.schema.node_schema import resolve_tree_schema


def generate_schema(node_tree_type, tree_schema=None, included_node_types=None) -> str:
    schema = resolve_tree_schema(node_tree_type, tree_schema=tree_schema)
    allowed_types = _normalize_included_types(schema, included_node_types)
    live_sockets_by_type = _collect_live_sockets_by_type(node_tree_type)
    lines: list[str] = []
    for node_type in sorted(allowed_types):
        node_schema = schema.node_types[node_type]
        live_inputs, live_outputs = live_sockets_by_type.get(node_type, (set(), set()))
        merged_inputs = _merge_sockets(node_schema.inputs, live_inputs)
        merged_outputs = _merge_sockets(node_schema.outputs, live_outputs)
        inputs = ", ".join(merged_inputs) or "-"
        outputs = ", ".join(merged_outputs) or "-"
        lines.append(f"{node_type}")
        lines.append(f"  inputs: {inputs}")
        lines.append(f"  outputs: {outputs}")
        if node_schema.properties:
            lines.append(f"  properties: {', '.join(sorted(node_schema.properties))}")
    return "\n".join(lines)


def generate_relevant_schema(node_tree, tree_schema=None) -> str:
    schema = resolve_tree_schema(node_tree, tree_schema=tree_schema)
    included_node_types = {node.bl_idname for node in getattr(node_tree, "nodes", [])}
    return generate_schema(node_tree, tree_schema=schema, included_node_types=included_node_types)


def _normalize_included_types(schema, included_node_types) -> set[str]:
    if included_node_types is None:
        return set(schema.node_types)
    return {node_type for node_type in included_node_types if node_type in schema.node_types}


def _collect_live_sockets_by_type(node_tree) -> dict[str, tuple[set[str], set[str]]]:
    if not hasattr(node_tree, "nodes"):
        return {}

    sockets_by_type: dict[str, tuple[set[str], set[str]]] = {}
    for node in getattr(node_tree, "nodes", []):
        node_type = getattr(node, "bl_idname", None)
        if not node_type:
            continue
        inputs, outputs = sockets_by_type.setdefault(node_type, (set(), set()))
        inputs.update(socket.name for socket in getattr(node, "inputs", []))
        outputs.update(socket.name for socket in getattr(node, "outputs", []))
    return sockets_by_type


def _merge_sockets(base: tuple[str, ...], extras: set[str]) -> tuple[str, ...]:
    ordered = list(base)
    for socket_name in sorted(extras):
        if socket_name not in ordered:
            ordered.append(socket_name)
    return tuple(ordered)
