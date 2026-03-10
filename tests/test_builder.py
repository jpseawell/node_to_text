from __future__ import annotations

import unittest

from node_to_text.graph.builder import _apply_assignment, _ensure_group_interface_sockets, _resolve_socket_for_link
from node_to_text.models import EdgeDef, GraphDefinition, InterfaceSocketDef, NodeDef


class EnsureGroupInterfaceSocketsTests(unittest.TestCase):
    def test_creates_missing_group_input_and_output_interface_sockets(self) -> None:
        node_tree = _NodeTree(
            [
                _Node("Group Input", "NodeGroupInput"),
                _Node(
                    "Cube",
                    "GeometryNodeMeshCube",
                    inputs=[("Size", "NodeSocketVector")],
                    outputs=[("Mesh", "NodeSocketGeometry")],
                ),
                _Node("Group Output", "NodeGroupOutput"),
            ]
        )
        graph = GraphDefinition(
            nodes=[
                NodeDef(id="Group Input", type="NodeGroupInput"),
                NodeDef(id="Cube", type="GeometryNodeMeshCube"),
                NodeDef(id="Group Output", type="NodeGroupOutput"),
            ],
            interface_sockets=[
                InterfaceSocketDef(direction="INPUT", name="Beam Depth", socket_type="NodeSocketVector"),
                InterfaceSocketDef(direction="OUTPUT", name="Geometry", socket_type="NodeSocketGeometry"),
            ],
            edges=[
                EdgeDef(
                    from_node="Group Input",
                    from_socket="Beam Depth",
                    to_node="Cube",
                    to_socket="Size",
                ),
                EdgeDef(
                    from_node="Cube",
                    from_socket="Mesh",
                    to_node="Group Output",
                    to_socket="Geometry",
                ),
            ],
        )

        _ensure_group_interface_sockets(graph, node_tree)

        self.assertEqual(
            sorted((item.in_out, item.name, item.socket_type) for item in node_tree.interface.items_tree),
            [
                ("INPUT", "Beam Depth", "NodeSocketVector"),
                ("OUTPUT", "Geometry", "NodeSocketGeometry"),
            ],
        )

    def test_ignores_none_assignments_for_direct_node_properties(self) -> None:
        node = _NodeWithOptionalSequenceProperty("Example", "ShaderNodeCombineXYZ")

        _apply_assignment(node, "location_absolute", None)

        self.assertEqual(node.location_absolute, (0.0, 0.0))

    def test_reconciles_changed_interface_socket_types(self) -> None:
        node_tree = _NodeTree([_Node("Group Input", "NodeGroupInput"), _Node("Group Output", "NodeGroupOutput")])
        node_tree.interface.items_tree = [
            _InterfaceItem("Beam Depth", "INPUT", "NodeSocketFloat"),
            _InterfaceItem("Geometry", "OUTPUT", "NodeSocketGeometry"),
            _InterfaceItem("Obsolete", "INPUT", "NodeSocketFloat"),
        ]
        graph = GraphDefinition(
            nodes=[NodeDef(id="Group Input", type="NodeGroupInput"), NodeDef(id="Group Output", type="NodeGroupOutput")],
            interface_sockets=[
                InterfaceSocketDef(direction="INPUT", name="Beam Depth", socket_type="NodeSocketVector"),
                InterfaceSocketDef(direction="OUTPUT", name="Geometry", socket_type="NodeSocketGeometry"),
            ],
        )

        from node_to_text.graph.builder import _finalize_group_interface

        _finalize_group_interface(graph, node_tree)

        self.assertEqual(
            sorted((item.in_out, item.name, item.socket_type) for item in node_tree.interface.items_tree),
            [
                ("INPUT", "Beam Depth", "NodeSocketVector"),
                ("OUTPUT", "Geometry", "NodeSocketGeometry"),
            ],
        )

    def test_resolves_missing_group_input_socket_during_link_creation(self) -> None:
        node_tree = _NodeTree(
            [
                _Node("Group Input", "NodeGroupInput"),
                _Node("Math.005", "ShaderNodeMath", inputs=[("Value", "NodeSocketFloat")]),
            ]
        )

        socket = _resolve_socket_for_link(
            node_tree,
            node=node_tree.nodes["Group Input"],
            socket_name="Beam Depth",
            is_output=True,
            counterpart_node=node_tree.nodes["Math.005"],
            counterpart_socket_name="Value",
        )

        self.assertEqual(socket.name, "Beam Depth")
        self.assertEqual(socket.bl_socket_idname, "NodeSocketFloat")


class _Socket:
    def __init__(self, name: str, socket_type: str):
        self.name = name
        self.bl_socket_idname = socket_type


class _Sockets(list):
    def get(self, name: str):
        for socket in self:
            if socket.name == name:
                return socket
        return None


class _Node:
    def __init__(self, name: str, bl_idname: str, inputs=None, outputs=None):
        self.name = name
        self.bl_idname = bl_idname
        self.inputs = _Sockets([_Socket(socket_name, socket_type) for socket_name, socket_type in (inputs or [])])
        self.outputs = _Sockets([_Socket(socket_name, socket_type) for socket_name, socket_type in (outputs or [])])


class _NodeWithOptionalSequenceProperty(_Node):
    def __init__(self, name: str, bl_idname: str):
        super().__init__(name, bl_idname)
        self._location_absolute = (0.0, 0.0)

    @property
    def location_absolute(self):
        return self._location_absolute

    @location_absolute.setter
    def location_absolute(self, value):
        if value is None:
            raise TypeError("sequence expected at dimension 1, not 'NoneType'")
        self._location_absolute = value


class _InterfaceItem:
    item_type = "SOCKET"

    def __init__(self, name: str, in_out: str, socket_type: str):
        self.name = name
        self.in_out = in_out
        self.socket_type = socket_type


class _Interface:
    def __init__(self):
        self.items_tree: list[_InterfaceItem] = []
        self.owner = None

    def new_socket(self, name: str, in_out: str, socket_type: str):
        self.items_tree.append(_InterfaceItem(name, in_out, socket_type))

    def remove(self, item):
        self.items_tree.remove(item)


class _Nodes(dict):
    def __init__(self, nodes: list[_Node]):
        super().__init__((node.name, node) for node in nodes)


class _NodeTree:
    def __init__(self, nodes: list[_Node]):
        self.nodes = _Nodes(nodes)
        self.interface = _Interface()
        self.interface.owner = self

    def interface_update(self, _context=None):
        group_input = self.nodes.get("Group Input")
        if group_input is not None:
            group_input.outputs = _Sockets(
                [
                    _Socket(item.name, item.socket_type)
                    for item in self.interface.items_tree
                    if item.in_out == "INPUT"
                ]
            )
        group_output = self.nodes.get("Group Output")
        if group_output is not None:
            group_output.inputs = _Sockets(
                [
                    _Socket(item.name, item.socket_type)
                    for item in self.interface.items_tree
                    if item.in_out == "OUTPUT"
                ]
            )


if __name__ == "__main__":
    unittest.main()