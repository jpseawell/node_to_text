from __future__ import annotations

import unittest

from node_to_text.dsl.parser import DSLParseError, extract_dsl_text, parse_dsl


class ParseDSLTests(unittest.TestCase):
    def test_parses_nodes_and_edges(self) -> None:
        graph = parse_dsl(
            """
            node noise ShaderNodeTexNoise scale=5 detail=2
            node bsdf ShaderNodeBsdfPrincipled roughness=0.4
            connect noise.Color -> bsdf.Base Color
            """
        )

        self.assertEqual([node.id for node in graph.nodes], ["noise", "bsdf"])
        self.assertEqual(graph.nodes[0].properties["scale"], 5)
        self.assertEqual(graph.edges[0].to_socket, "Base Color")

    def test_parses_quoted_strings(self) -> None:
        graph = parse_dsl('node ramp ShaderNodeValToRGB label="Edge Wear"')
        self.assertEqual(graph.nodes[0].properties["label"], "Edge Wear")

    def test_parses_spaced_node_ids_and_input_names(self) -> None:
        graph = parse_dsl(
            'node "Principled BSDF" ShaderNodeBsdfPrincipled Base Color=(1,0,0,1)\n'
            'connect "Principled BSDF".BSDF -> "Material Output".Surface'
        )

        self.assertEqual(graph.nodes[0].id, "Principled BSDF")
        self.assertEqual(graph.nodes[0].properties["Base Color"], (1, 0, 0, 1))
        self.assertEqual(graph.edges[0].to_node, "Material Output")

    def test_reports_invalid_syntax(self) -> None:
        with self.assertRaises(DSLParseError) as context:
            parse_dsl("connect missing_arrow")

        self.assertEqual(context.exception.errors[0].line_number, 1)

    def test_reports_schema_like_output_clearly(self) -> None:
        text = """Output: ShaderNodeBsdfPrincipled
        inputs: Base Color, Roughness
        outputs: BSDF"""

        with self.assertRaises(DSLParseError) as context:
            parse_dsl(text)

        self.assertEqual(context.exception.errors[0].error_type, "SchemaLikeOutput")
        self.assertIn("Return only lines starting with 'node' or 'connect'", context.exception.errors[0].description)

    def test_extracts_dsl_from_fenced_response(self) -> None:
        text = """Here is the updated graph:

```dsl
node bsdf ShaderNodeBsdfPrincipled roughness=0.2
node out ShaderNodeOutputMaterial
connect bsdf.BSDF -> out.Surface
```"""

        extracted = extract_dsl_text(text)

        self.assertEqual(
            extracted,
            "node bsdf ShaderNodeBsdfPrincipled roughness=0.2\n"
            "node out ShaderNodeOutputMaterial\n"
            "connect bsdf.BSDF -> out.Surface",
        )

    def test_parses_dsl_from_mixed_response_text(self) -> None:
        graph = parse_dsl(
            """Updated graph below.
            node bsdf ShaderNodeBsdfPrincipled roughness=0.2
            node out ShaderNodeOutputMaterial
            connect bsdf.BSDF -> out.Surface
            Hope this helps."""
        )

        self.assertEqual(len(graph.nodes), 2)


if __name__ == "__main__":
    unittest.main()
