from __future__ import annotations

import unittest

from node_to_text.graph.diff_engine import compute_diff
from node_to_text.models import EdgeDef, GraphDefinition, NodeDef


class ComputeDiffTests(unittest.TestCase):
    def test_detects_node_property_and_link_changes(self) -> None:
        existing = GraphDefinition(
            nodes=[
                NodeDef(id="noise", type="ShaderNodeTexNoise", properties={"scale": 5}),
                NodeDef(id="bsdf", type="ShaderNodeBsdfPrincipled", properties={"roughness": 0.5}),
            ],
            edges=[EdgeDef(from_node="noise", from_socket="Color", to_node="bsdf", to_socket="Base Color")],
        )
        updated = GraphDefinition(
            nodes=[
                NodeDef(id="noise", type="ShaderNodeTexNoise", properties={"scale": 8}),
                NodeDef(id="mix", type="ShaderNodeMix", properties={}),
                NodeDef(id="bsdf", type="ShaderNodeBsdfPrincipled", properties={}),
            ],
            edges=[EdgeDef(from_node="mix", from_socket="Result", to_node="bsdf", to_socket="Base Color")],
        )

        diff = compute_diff(existing, updated)

        self.assertEqual(diff.nodes_to_remove, [])
        self.assertEqual([node.id for node in diff.nodes_to_add], ["mix"])
        self.assertEqual(
            {(change.node_id, change.property_name, change.value, change.clear) for change in diff.property_changes},
            {
                ("bsdf", "roughness", None, True),
                ("noise", "scale", 8, False),
            },
        )
        self.assertEqual(len(diff.links_to_remove), 1)
        self.assertEqual(len(diff.links_to_add), 1)

    def test_replaces_nodes_when_type_changes(self) -> None:
        existing = GraphDefinition(nodes=[NodeDef(id="node", type="TypeA")])
        updated = GraphDefinition(nodes=[NodeDef(id="node", type="TypeB")])

        diff = compute_diff(existing, updated)

        self.assertEqual(diff.nodes_to_remove, ["node"])
        self.assertEqual([node.type for node in diff.nodes_to_add], ["TypeB"])


if __name__ == "__main__":
    unittest.main()
