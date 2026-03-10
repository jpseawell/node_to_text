"""Shared data models for the Node to Text pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union

PrimitiveValue = Union[str, int, float, bool, None, tuple, list]


@dataclass(frozen=True)
class InterfaceSocketDef:
    direction: str
    name: str
    socket_type: str
    line_number: int | None = None

    def key(self) -> tuple[str, str]:
        return (self.direction, self.name)


@dataclass(frozen=True)
class NodeDef:
    id: str
    type: str
    properties: dict[str, PrimitiveValue] = field(default_factory=dict)
    line_number: int | None = None


@dataclass(frozen=True)
class EdgeDef:
    from_node: str
    from_socket: str
    to_node: str
    to_socket: str
    line_number: int | None = None

    def key(self) -> tuple[str, str, str, str]:
        return (self.from_node, self.from_socket, self.to_node, self.to_socket)


@dataclass(frozen=True)
class GraphDefinition:
    nodes: list[NodeDef] = field(default_factory=list)
    edges: list[EdgeDef] = field(default_factory=list)
    tree_type: str | None = None
    interface_sockets: list[InterfaceSocketDef] = field(default_factory=list)

    def node_map(self) -> dict[str, NodeDef]:
        return {node.id: node for node in self.nodes}

    def edge_map(self) -> dict[tuple[str, str, str, str], EdgeDef]:
        return {edge.key(): edge for edge in self.edges}

    def interface_map(self) -> dict[tuple[str, str], InterfaceSocketDef]:
        return {socket.key(): socket for socket in self.interface_sockets}


@dataclass(frozen=True)
class ValidationError:
    line_number: int | None
    error_type: str
    description: str

    def __str__(self) -> str:
        location = f"Line {self.line_number}" if self.line_number is not None else "Line ?"
        return f"{location}: {self.error_type}: {self.description}"


@dataclass(frozen=True)
class PropertySchema:
    name: str
    value_type: str
    default: PrimitiveValue = None
    enum_values: tuple[str, ...] = ()


@dataclass(frozen=True)
class NodeTypeSchema:
    type_name: str
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    properties: dict[str, PropertySchema] = field(default_factory=dict)


@dataclass(frozen=True)
class NodeTreeSchema:
    tree_type: str
    node_types: dict[str, NodeTypeSchema] = field(default_factory=dict)


@dataclass(frozen=True)
class PropertyChange:
    node_id: str
    property_name: str
    value: PrimitiveValue = None
    clear: bool = False


@dataclass(frozen=True)
class GraphDiff:
    nodes_to_add: list[NodeDef] = field(default_factory=list)
    nodes_to_remove: list[str] = field(default_factory=list)
    property_changes: list[PropertyChange] = field(default_factory=list)
    links_to_add: list[EdgeDef] = field(default_factory=list)
    links_to_remove: list[EdgeDef] = field(default_factory=list)
