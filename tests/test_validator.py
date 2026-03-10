from __future__ import annotations

import unittest

from node_to_text.dsl.parser import parse_dsl
from node_to_text.dsl.validator import validate_graph
from node_to_text.schema.node_schema import build_schema


SCHEMA = build_schema(
    "ShaderNodeTree",
    {
        "ShaderNodeTexNoise": {
            "inputs": ("Vector", "Scale", "Detail"),
            "outputs": ("Color", "Fac"),
            "properties": {
                "scale": {"value_type": "float", "default": 0.0},
                "detail": {"value_type": "float", "default": 0.0},
            },
        },
        "ShaderNodeBsdfPrincipled": {
            "inputs": ("Base Color", "Roughness"),
            "outputs": ("BSDF",),
            "properties": {
                "roughness": {"value_type": "float", "default": 0.5},
            },
        },
    },
)


class ValidateGraphTests(unittest.TestCase):
    def test_accepts_valid_graph(self) -> None:
        graph = parse_dsl(
            """
            node noise ShaderNodeTexNoise scale=5 detail=2
            node bsdf ShaderNodeBsdfPrincipled roughness=0.4
            connect noise.Color -> bsdf.Base Color
            """
        )

        errors = validate_graph(graph, "ShaderNodeTree", tree_schema=SCHEMA)

        self.assertEqual(errors, [])

    def test_rejects_invalid_socket(self) -> None:
        graph = parse_dsl(
            """
            node noise ShaderNodeTexNoise scale=5
            node bsdf ShaderNodeBsdfPrincipled
            connect noise.ColorOut -> bsdf.Base Color
            """
        )

        errors = validate_graph(graph, "ShaderNodeTree", tree_schema=SCHEMA)

        self.assertEqual(errors[0].error_type, "UnknownSocket")

    def test_rejects_unknown_node_type(self) -> None:
        graph = parse_dsl("node noise ImaginaryNodeType")

        errors = validate_graph(graph, "ShaderNodeTree", tree_schema=SCHEMA)

        self.assertEqual(errors[0].error_type, "UnknownNodeType")

    def test_accepts_input_default_assignments(self) -> None:
        graph = parse_dsl(
            'node "Principled BSDF" ShaderNodeBsdfPrincipled Base Color=(1,0,0,1)'
        )

        errors = validate_graph(graph, "ShaderNodeTree", tree_schema=SCHEMA)

        self.assertEqual(errors, [])

    def test_accepts_live_dynamic_group_input_assignment(self) -> None:
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
        graph = parse_dsl('node group ShaderNodeGroup Color 1=(1,0,0,1)')
        node_tree = _NodeTreeWithSockets(
            [
                _NodeWithSockets(
                    name="group",
                    bl_idname="ShaderNodeGroup",
                    inputs=["Color 1"],
                    outputs=["Shader"],
                )
            ]
        )

        errors = validate_graph(graph, node_tree, tree_schema=group_schema)

        self.assertEqual(errors, [])

    def test_accepts_inferred_group_input_output_sockets_from_graph_edges(self) -> None:
        group_schema = build_schema(
            "GeometryNodeTree",
            {
                "NodeGroupInput": {
                    "inputs": (),
                    "outputs": (),
                    "properties": {},
                },
                "NodeGroupOutput": {
                    "inputs": (),
                    "outputs": (),
                    "properties": {},
                },
                "GeometryNodeMeshCube": {
                    "inputs": ("Size",),
                    "outputs": ("Mesh",),
                    "properties": {},
                },
            },
        )
        graph = parse_dsl(
            'node "Group Input" NodeGroupInput\n'
            'node cube GeometryNodeMeshCube\n'
            'node "Group Output" NodeGroupOutput\n'
            'connect "Group Input".Beam Depth -> cube.Size\n'
            'connect cube.Mesh -> "Group Output".Geometry'
        )

        errors = validate_graph(graph, "GeometryNodeTree", tree_schema=group_schema)

        self.assertEqual(errors, [])

    def test_accepts_declared_interface_sockets_without_live_tree_state(self) -> None:
        group_schema = build_schema(
            "GeometryNodeTree",
            {
                "NodeGroupInput": {
                    "inputs": (),
                    "outputs": (),
                    "properties": {},
                },
                "NodeGroupOutput": {
                    "inputs": (),
                    "outputs": (),
                    "properties": {},
                },
                "GeometryNodeMeshCube": {
                    "inputs": ("Size",),
                    "outputs": ("Mesh",),
                    "properties": {},
                },
            },
        )
        graph = parse_dsl(
            'tree GeometryNodeTree\n'
            'interface input "Beam Depth" NodeSocketVector\n'
            'interface output Geometry NodeSocketGeometry\n'
            'node "Group Input" NodeGroupInput\n'
            'node cube GeometryNodeMeshCube\n'
            'node "Group Output" NodeGroupOutput\n'
            'connect "Group Input"."Beam Depth" -> cube.Size\n'
            'connect cube.Mesh -> "Group Output".Geometry'
        )

        errors = validate_graph(graph, "GeometryNodeTree", tree_schema=group_schema)

        self.assertEqual(errors, [])

    def test_rejects_mismatched_tree_type(self) -> None:
        graph = parse_dsl('tree GeometryNodeTree\nnode noise ShaderNodeTexNoise')

        errors = validate_graph(graph, "ShaderNodeTree", tree_schema=SCHEMA)

        self.assertEqual(errors[0].error_type, "GraphTypeMismatch")


class _Socket:
    def __init__(self, name: str):
        self.name = name


class _NodeWithSockets:
    def __init__(self, name: str, bl_idname: str, inputs: list[str], outputs: list[str]):
        self.name = name
        self.bl_idname = bl_idname
        self.inputs = [_Socket(input_name) for input_name in inputs]
        self.outputs = [_Socket(output_name) for output_name in outputs]


class _NodeTreeWithSockets:
    bl_idname = "ShaderNodeTree"

    def __init__(self, nodes):
        self.nodes = nodes


if __name__ == "__main__":
    unittest.main()
