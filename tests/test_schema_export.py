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
        self.inputs = []
        self.outputs = []


class _Socket:
    def __init__(self, name: str):
        self.name = name


class _SocketNode(_Node):
    def __init__(self, bl_idname: str, inputs: list[str], outputs: list[str]):
        super().__init__(bl_idname)
        self.inputs = [_Socket(input_name) for input_name in inputs]
        self.outputs = [_Socket(output_name) for output_name in outputs]


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

    def test_generate_relevant_schema_includes_live_dynamic_sockets(self) -> None:
        group_schema = build_schema(
            "ShaderNodeTree",
            {
                "ShaderNodeGroup": {
                    "inputs": (),
                    "outputs": (),
                    "properties": {},
                }
            },
        )
        node_tree = _NodeTree([])
        node_tree.nodes = [_SocketNode("ShaderNodeGroup", ["Color 1", "Knots"], ["Shader"])]

        text = generate_relevant_schema(node_tree, tree_schema=group_schema)

        self.assertIn("inputs: Color 1, Knots", text)
        self.assertIn("outputs: Shader", text)


if __name__ == "__main__":
    unittest.main()
