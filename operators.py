"""Blender operators for DSL export, validation, and apply flows."""

from __future__ import annotations

import bpy  # type: ignore

from node_to_text.dsl.parser import DSLParseError, parse_dsl
from node_to_text.dsl.serializer import export_node_tree
from node_to_text.dsl.validator import GraphValidationError, raise_for_errors, validate_graph
from node_to_text.graph.builder import apply_graph
from node_to_text.graph.node_utils import get_active_node_tree
from node_to_text.schema.schema_export import generate_relevant_schema, generate_schema
from node_to_text.utils.clipboard import copy_to_clipboard, paste_from_clipboard
from node_to_text.utils.text_blocks import (
    EXAMPLE_DSL,
    build_edit_prompt,
    build_prompt_template,
    write_text_block,
)


def _format_errors(errors) -> str:
    return "\n".join(str(error) for error in errors)


class NODE_DSL_OT_export_graph(bpy.types.Operator):
    bl_idname = "node_dsl.export_graph"
    bl_label = "Export Current Graph"
    bl_description = "Copy an LLM-ready editing bundle for the active node tree"

    def execute(self, context):
        node_tree = get_active_node_tree(context)
        current_graph_dsl = export_node_tree(node_tree)
        schema_text = generate_relevant_schema(node_tree)
        text = build_edit_prompt(current_graph_dsl, schema_text)
        copy_to_clipboard(text, context)
        write_text_block("node_dsl_export", text, bpy)
        self.report({"INFO"}, "Copied LLM-ready graph export to the clipboard.")
        return {"FINISHED"}


class NODE_DSL_OT_validate_clipboard(bpy.types.Operator):
    bl_idname = "node_dsl.validate_clipboard"
    bl_label = "Validate DSL From Clipboard"
    bl_description = "Validate DSL from the clipboard against the active node tree type"

    def execute(self, context):
        node_tree = get_active_node_tree(context)
        text = paste_from_clipboard(context)
        try:
            graph = parse_dsl(text)
            raise_for_errors(validate_graph(graph, node_tree))
        except DSLParseError as exc:
            write_text_block("node_dsl_validation_errors", _format_errors(exc.errors), bpy)
            self.report({"ERROR"}, str(exc.errors[0]))
            return {"CANCELLED"}
        except GraphValidationError as exc:
            write_text_block("node_dsl_validation_errors", _format_errors(exc.errors), bpy)
            self.report({"ERROR"}, str(exc.errors[0]))
            return {"CANCELLED"}

        self.report({"INFO"}, "DSL is valid for the active node tree.")
        return {"FINISHED"}


class NODE_DSL_OT_apply_clipboard(bpy.types.Operator):
    bl_idname = "node_dsl.apply_clipboard"
    bl_label = "Import From Clipboard"
    bl_description = "Validate and import DSL from the clipboard into the active node tree"

    def execute(self, context):
        node_tree = get_active_node_tree(context)
        text = paste_from_clipboard(context)
        try:
            graph = parse_dsl(text)
            raise_for_errors(validate_graph(graph, node_tree))
            apply_graph(graph, node_tree)
        except DSLParseError as exc:
            write_text_block("node_dsl_apply_errors", _format_errors(exc.errors), bpy)
            self.report({"ERROR"}, str(exc.errors[0]))
            return {"CANCELLED"}
        except GraphValidationError as exc:
            write_text_block("node_dsl_apply_errors", _format_errors(exc.errors), bpy)
            self.report({"ERROR"}, str(exc.errors[0]))
            return {"CANCELLED"}
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        self.report({"INFO"}, "Imported DSL into the active node tree.")
        return {"FINISHED"}


class NODE_DSL_OT_copy_schema(bpy.types.Operator):
    bl_idname = "node_dsl.copy_schema"
    bl_label = "Copy DSL Schema"
    bl_description = "Copy the active node tree schema to the clipboard"

    def execute(self, context):
        node_tree = get_active_node_tree(context)
        text = generate_schema(node_tree)
        copy_to_clipboard(text, context)
        write_text_block("node_dsl_schema", text, bpy)
        self.report({"INFO"}, "Copied schema to the clipboard.")
        return {"FINISHED"}


class NODE_DSL_OT_copy_relevant_schema(bpy.types.Operator):
    bl_idname = "node_dsl.copy_relevant_schema"
    bl_label = "Copy Relevant Schema"
    bl_description = "Copy schema only for node types used in the active graph"

    def execute(self, context):
        node_tree = get_active_node_tree(context)
        text = generate_relevant_schema(node_tree)
        copy_to_clipboard(text, context)
        write_text_block("node_dsl_relevant_schema", text, bpy)
        self.report({"INFO"}, "Copied relevant schema to the clipboard.")
        return {"FINISHED"}


class NODE_DSL_OT_copy_example(bpy.types.Operator):
    bl_idname = "node_dsl.copy_example"
    bl_label = "Copy Example DSL"
    bl_description = "Copy an example DSL snippet to the clipboard"

    def execute(self, context):
        copy_to_clipboard(EXAMPLE_DSL, context)
        write_text_block("node_dsl_example", EXAMPLE_DSL, bpy)
        self.report({"INFO"}, "Copied example DSL to the clipboard.")
        return {"FINISHED"}


class NODE_DSL_OT_copy_prompt(bpy.types.Operator):
    bl_idname = "node_dsl.copy_prompt"
    bl_label = "Copy Edit Prompt"
    bl_description = "Copy an LLM-ready prompt with the current graph and relevant schema"

    def execute(self, context):
        node_tree = get_active_node_tree(context)
        current_graph_dsl = export_node_tree(node_tree)
        schema_text = generate_relevant_schema(node_tree)
        prompt = build_edit_prompt(current_graph_dsl, schema_text)
        copy_to_clipboard(prompt, context)
        write_text_block("node_dsl_prompt", prompt, bpy)
        self.report({"INFO"}, "Copied edit prompt to the clipboard.")
        return {"FINISHED"}


CLASSES = (
    NODE_DSL_OT_export_graph,
    NODE_DSL_OT_validate_clipboard,
    NODE_DSL_OT_apply_clipboard,
    NODE_DSL_OT_copy_schema,
    NODE_DSL_OT_copy_relevant_schema,
    NODE_DSL_OT_copy_example,
    NODE_DSL_OT_copy_prompt,
)


def register() -> None:
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
