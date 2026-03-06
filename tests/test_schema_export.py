from __future__ import annotations

import unittest

from node_to_text.schema.node_schema import build_schema
from node_to_text.schema.schema_export import generate_relevant_schema, generate_schema


SCHEMA = build_schema(
    "ShaderNodeTree",
    {
        "ShaderNodeBsdfPrincipled": {
            "inputs": ("Base Color", "Roughness"),
            "outputs": ("BSDF",),
            "properties": {
                "roughness": {"value_type": "float", "default": 0.5},
            },
        },
        "ShaderNodeTexNoise": {
            "inputs": ("Vector", "Scale", "Detail"),
            "outputs": ("Color", "Fac"),
            "properties": {
                "scale": {"value_type": "float", "default": 0.0},
            },
        },
        "ShaderNodeValToRGB": {
            "inputs": ("Fac",),
            "outputs": ("Color",),
            "properties": {},
        },
    },
)


class _Node:
    def __init__(self, bl_idname: str):
        self.bl_idname = bl_idname


class _NodeTree:
    bl_idname = "ShaderNodeTree"

    def __init__(self, node_types):
        self.nodes = [_Node(node_type) for node_type in node_types]


class SchemaExportTests(unittest.TestCase):
    def test_generate_schema_can_filter_node_types(self) -> None:
        text = generate_schema(
            "ShaderNodeTree",
            tree_schema=SCHEMA,
            included_node_types={"ShaderNodeTexNoise", "MissingNodeType"},
        )

        self.assertIn("ShaderNodeTexNoise", text)
        self.assertNotIn("ShaderNodeBsdfPrincipled", text)

    def test_generate_relevant_schema_uses_active_graph_node_types(self) -> None:
        node_tree = _NodeTree(["ShaderNodeValToRGB", "ShaderNodeTexNoise", "ShaderNodeTexNoise"])

        text = generate_relevant_schema(node_tree, tree_schema=SCHEMA)

        self.assertIn("ShaderNodeTexNoise", text)
        self.assertIn("ShaderNodeValToRGB", text)
        self.assertNotIn("ShaderNodeBsdfPrincipled", text)


if __name__ == "__main__":
    unittest.main()
