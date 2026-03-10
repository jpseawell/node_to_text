"""Prompt and text-block helpers."""

from __future__ import annotations

EXAMPLE_DSL = """tree ShaderNodeTree
node noise ShaderNodeTexNoise scale=5 detail=2
node ramp ShaderNodeValToRGB
node bsdf ShaderNodeBsdfPrincipled roughness=0.4
connect noise.Color -> ramp.Fac
connect ramp.Color -> bsdf.Base Color"""


def build_prompt_template(schema_text: str) -> str:
    sections = [
        "You generate Blender node graphs using the DSL below.",
        "",
        "DSL Syntax:",
        "tree <tree_type>",
        "interface <input|output> <name> <socket_type>",
        "node <id> <node_type> <property>=<value>",
        "connect <node>.<output> -> <node>.<input>",
        "",
        "Rules:",
        "- Do not invent node types",
        "- Preserve the exported tree line unless you are intentionally converting graph types",
        "- Preserve interface lines unless the task changes the group interface",
        "- Use valid socket names",
        "- Preserve stable node ids",
        "- Output only DSL",
    ]
    if schema_text:
        sections.extend(["", "Available schema:", schema_text])
    return "\n".join(sections)


def build_edit_prompt(current_graph_dsl: str, schema_text: str) -> str:
    sections = [
        "You are editing an existing Blender node graph.",
        "Return the modified graph as valid Node to Text.",
        "",
        "DSL Syntax:",
        "tree <tree_type>",
        "interface <input|output> <name> <socket_type>",
        "node <id> <node_type> <property>=<value>",
        "connect <node>.<output> -> <node>.<input>",
        "",
        "Rules:",
        "- Preserve the tree line unless the task explicitly changes node graph type",
        "- Preserve interface lines unless the task changes the group interface",
        "- Preserve existing node ids unless explicitly asked to rename them",
        "- Do not invent node types, property names, or socket names",
        "- Keep valid existing connections unless the task requires changing them",
        "- Output only the modified DSL",
        "- Prefer a ```dsl fenced code block``` or raw DSL text",
        "- Every node line must start with 'node' and every link line must start with 'connect'",
    ]
    if schema_text:
        sections.extend(["", "Relevant schema:", schema_text])
    sections.extend(
        [
            "",
            "Current graph DSL:",
            current_graph_dsl,
            "",
            "Your task:",
            "<Describe the graph change you want here>",
            "",
            "Return format:",
            "```dsl",
            "tree <tree_type>",
            "interface <input|output> <name> <socket_type>",
            "node <id> <node_type> <property>=<value>",
            "connect <node>.<output> -> <node>.<input>",
            "```",
            "",
            "Modified DSL:",
        ]
    )
    return "\n".join(sections)


def write_text_block(name: str, text: str, bpy_module=None):
    bpy_module = bpy_module
    if bpy_module is None:
        try:
            import bpy as bpy_module  # type: ignore
        except ImportError:  # pragma: no cover - Blender-only import
            return None
    text_block = bpy_module.data.texts.get(name)
    if text_block is None:
        text_block = bpy_module.data.texts.new(name)
    text_block.clear()
    text_block.write(text)
    return text_block
