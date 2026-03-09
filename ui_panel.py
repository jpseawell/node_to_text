"""UI panel for the Node to Text tools."""

from __future__ import annotations

import bpy  # type: ignore

from node_to_text.graph.node_utils import get_active_node_tree

try:
    from node_to_text import __version__ as ADDON_VERSION
except ImportError:  # pragma: no cover - Blender packaging edge case
    ADDON_VERSION = "unknown"


class NODE_DSL_PT_panel(bpy.types.Panel):
    bl_label = "Node to Text"
    bl_idname = "NODE_DSL_PT_panel"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Node to Text"

    @classmethod
    def poll(cls, context):
        try:
            get_active_node_tree(context)
        except ValueError:
            return False
        return True

    def draw(self, context):
        layout = self.layout
        column = layout.column(align=True)
        column.operator("node_dsl.export_graph")
        column.operator("node_dsl.apply_clipboard")
        layout.separator()
        layout.label(text=f"Version: v{ADDON_VERSION}")


CLASSES = (NODE_DSL_PT_panel,)


def register() -> None:
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
