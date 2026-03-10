from __future__ import annotations

import unittest

from node_to_text.dsl.parser import parse_dsl
from node_to_text.dsl.serializer import serialize_graph
from node_to_text.models import EdgeDef, GraphDefinition, InterfaceSocketDef, NodeDef


class SerializeGraphTests(unittest.TestCase):
    def test_serializes_deterministically(self) -> None:
        graph = GraphDefinition(
            nodes=[
                NodeDef(id="b", type="NodeTypeB"),
                NodeDef(id="node a", type="NodeTypeA", properties={"Base Color": (1, 0, 0, 1), "scale": 2}),
            ],
            edges=[EdgeDef(from_node="b", from_socket="Color", to_node="node a", to_socket="Base Color")],
            tree_type="ShaderNodeTree",
            interface_sockets=[
                InterfaceSocketDef(direction="INPUT", name="Tint", socket_type="NodeSocketColor"),
                InterfaceSocketDef(direction="OUTPUT", name="Shader", socket_type="NodeSocketShader"),
            ],
        )

        text = serialize_graph(graph)

        self.assertEqual(
            text,
            "tree ShaderNodeTree\n"
            'interface input Tint NodeSocketColor\n'
            'interface output Shader NodeSocketShader\n'
            "node b NodeTypeB\n"
            'node "node a" NodeTypeA Base Color=(1,0,0,1) scale=2\n'
            'connect b.Color -> "node a".Base Color',
        )

    def test_round_trip_is_stable(self) -> None:
        source = (
            'tree ShaderNodeTree\n'
            'node "Material Output" ShaderNodeOutputMaterial\n'
            'node "Principled BSDF" ShaderNodeBsdfPrincipled Base Color=(1,0,0,1) roughness=0.4\n'
            'connect "Principled BSDF".BSDF -> "Material Output".Surface'
        )

        serialized = serialize_graph(parse_dsl(source))

        self.assertEqual(serialized, source)

    def test_round_trip_preserves_interface_declarations(self) -> None:
        source = (
            'tree GeometryNodeTree\n'
            'interface input "Beam Depth" NodeSocketFloat\n'
            'interface output Geometry NodeSocketGeometry\n'
            'node "Group Input" NodeGroupInput\n'
            'node "Group Output" NodeGroupOutput\n'
            'connect "Group Input".Beam Depth -> "Group Output".Geometry'
        )

        serialized = serialize_graph(parse_dsl(source))

        self.assertEqual(serialized, source)


if __name__ == "__main__":
    unittest.main()
