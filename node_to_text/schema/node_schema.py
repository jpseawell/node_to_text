"""Schema helpers for supported Blender node trees."""

from __future__ import annotations

import inspect
from functools import lru_cache

from node_to_text.models import NodeTreeSchema, NodeTypeSchema, PropertySchema

SUPPORTED_TREE_TYPES = ("ShaderNodeTree", "GeometryNodeTree", "CompositorNodeTree")
_SKIP_PROPERTIES = {
    "bl_description",
    "bl_height_default",
    "bl_height_max",
    "bl_height_min",
    "bl_icon",
    "bl_idname",
    "bl_label",
    "bl_static_type",
    "bl_width_default",
    "bl_width_max",
    "bl_width_min",
    "color",
    "dimensions",
    "height",
    "inputs",
    "internal_links",
    "is_active_output",
    "location",
    "mute",
    "name",
    "outputs",
    "parent",
    "rna_type",
    "select",
    "show_options",
    "show_preview",
    "show_texture",
    "type",
    "use_custom_color",
    "width",
}

try:
    import bpy  # type: ignore
except ImportError:  # pragma: no cover - Blender-only import
    bpy = None


def resolve_tree_schema(node_tree_or_type, tree_schema=None) -> NodeTreeSchema:
    if isinstance(tree_schema, NodeTreeSchema):
        return tree_schema
    if isinstance(node_tree_or_type, NodeTreeSchema):
        return node_tree_or_type
    if hasattr(node_tree_or_type, "bl_idname"):
        return introspect_tree_schema(node_tree_or_type.bl_idname)
    if isinstance(node_tree_or_type, str):
        return introspect_tree_schema(node_tree_or_type)
    raise TypeError("A supported node tree, tree type string, or NodeTreeSchema is required.")


@lru_cache(maxsize=None)
def introspect_tree_schema(tree_type: str) -> NodeTreeSchema:
    if bpy is None:
        raise RuntimeError("Blender schema introspection requires bpy.")
    if tree_type not in SUPPORTED_TREE_TYPES:
        raise ValueError(f"Unsupported node tree type {tree_type!r}.")

    if tree_type == "CompositorNodeTree":
        owner = bpy.data.scenes.new(name="__node_dsl_schema__")
        owner.use_nodes = True
        node_tree = owner.node_tree
        cleanup = lambda: bpy.data.scenes.remove(owner)
    else:
        owner = bpy.data.node_groups.new(name="__node_dsl_schema__", type=tree_type)
        node_tree = owner
        cleanup = lambda: bpy.data.node_groups.remove(owner)

    node_types: dict[str, NodeTypeSchema] = {}
    try:
        for _, candidate in inspect.getmembers(bpy.types, inspect.isclass):
            if not issubclass(candidate, bpy.types.Node):
                continue
            identifier = getattr(getattr(candidate, "bl_rna", None), "identifier", None)
            if not identifier:
                continue
            try:
                node = node_tree.nodes.new(identifier)
            except RuntimeError:
                continue
            try:
                node_types[identifier] = _introspect_node_type(node)
            finally:
                node_tree.nodes.remove(node)
    finally:
        cleanup()

    return NodeTreeSchema(tree_type=tree_type, node_types=node_types)


def build_schema(tree_type: str, node_types: dict[str, dict]) -> NodeTreeSchema:
    converted: dict[str, NodeTypeSchema] = {}
    for node_type, data in node_types.items():
        properties = {
            property_name: PropertySchema(
                name=property_name,
                value_type=property_data.get("value_type", "string"),
                default=property_data.get("default"),
                enum_values=tuple(property_data.get("enum_values", ())),
            )
            for property_name, property_data in data.get("properties", {}).items()
        }
        converted[node_type] = NodeTypeSchema(
            type_name=node_type,
            inputs=tuple(data.get("inputs", ())),
            outputs=tuple(data.get("outputs", ())),
            properties=properties,
        )
    return NodeTreeSchema(tree_type=tree_type, node_types=converted)


def _introspect_node_type(node) -> NodeTypeSchema:
    properties: dict[str, PropertySchema] = {}
    for property_definition in node.bl_rna.properties:
        property_name = property_definition.identifier
        if property_name in _SKIP_PROPERTIES:
            continue
        if getattr(property_definition, "is_hidden", False) or getattr(property_definition, "is_readonly", False):
            continue

        property_schema = _make_property_schema(property_definition)
        if property_schema is not None:
            properties[property_name] = property_schema

    return NodeTypeSchema(
        type_name=node.bl_idname,
        inputs=tuple(socket.name for socket in node.inputs),
        outputs=tuple(socket.name for socket in node.outputs),
        properties=properties,
    )


def _make_property_schema(property_definition) -> PropertySchema | None:
    property_type = property_definition.type
    if property_type == "BOOLEAN":
        default = bool(property_definition.default)
        value_type = "bool"
        enum_values: tuple[str, ...] = ()
    elif property_type == "INT":
        default = int(property_definition.default)
        value_type = "int"
        enum_values = ()
    elif property_type == "FLOAT":
        default = float(property_definition.default)
        value_type = "float"
        enum_values = ()
    elif property_type == "STRING":
        default = str(property_definition.default)
        value_type = "string"
        enum_values = ()
    elif property_type == "ENUM":
        default = str(property_definition.default)
        value_type = "enum"
        enum_values = tuple(item.identifier for item in property_definition.enum_items)
    else:
        return None

    return PropertySchema(
        name=property_definition.identifier,
        value_type=value_type,
        default=default,
        enum_values=enum_values,
    )
