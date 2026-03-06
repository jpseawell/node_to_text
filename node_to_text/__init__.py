"""Node to Text add-on package."""

from __future__ import annotations

bl_info = {
    "name": "Node to Text",
    "author": "GitHub Copilot",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "Node Editor > Sidebar > Node to Text",
    "description": "Round-trip Blender node graphs through a deterministic DSL.",
    "category": "Node",
}

try:
    import bpy  # type: ignore
except ImportError:  # pragma: no cover - Blender-only import
    bpy = None

if bpy is not None:  # pragma: no branch - simple import gate
    from . import operators, ui_panel


def register() -> None:
    if bpy is None:
        return
    operators.register()
    ui_panel.register()


def unregister() -> None:
    if bpy is None:
        return
    ui_panel.unregister()
    operators.unregister()
