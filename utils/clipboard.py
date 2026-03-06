"""Clipboard integration helpers."""

from __future__ import annotations

try:
    import bpy  # type: ignore
except ImportError:  # pragma: no cover - Blender-only import
    bpy = None

_clipboard_fallback = ""


def copy_to_clipboard(text: str, context=None) -> None:
    global _clipboard_fallback
    _clipboard_fallback = text
    if context is not None:
        context.window_manager.clipboard = text
        return
    if bpy is not None:
        bpy.context.window_manager.clipboard = text


def paste_from_clipboard(context=None) -> str:
    if context is not None:
        return context.window_manager.clipboard
    if bpy is not None:
        return bpy.context.window_manager.clipboard
    return _clipboard_fallback
