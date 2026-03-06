from __future__ import annotations

import unittest

from node_to_text.utils.text_blocks import build_edit_prompt


class TextBlockTests(unittest.TestCase):
    def test_build_edit_prompt_includes_graph_and_schema(self) -> None:
        prompt = build_edit_prompt(
            "node bsdf ShaderNodeBsdfPrincipled roughness=0.4",
            "ShaderNodeBsdfPrincipled\n  inputs: Base Color",
        )

        self.assertIn("Current graph DSL:", prompt)
        self.assertIn("node bsdf ShaderNodeBsdfPrincipled roughness=0.4", prompt)
        self.assertIn("Relevant schema:", prompt)
        self.assertIn("Prefer a ```dsl fenced code block``` or raw DSL text", prompt)
        self.assertIn("<Describe the graph change you want here>", prompt)


if __name__ == "__main__":
    unittest.main()
