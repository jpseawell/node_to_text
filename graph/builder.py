"""Apply validated graph definitions to Blender node trees."""

from __future__ import annotations

from node_to_text.graph.diff_engine import compute_diff
from node_to_text.graph.node_utils import find_node, get_socket, graph_from_node_tree
from node_to_text.models import GraphDefinition, GraphDiff, InterfaceSocketDef
from node_to_text.schema.node_schema import resolve_tree_schema


def apply_graph(graph_def: GraphDefinition, node_tree, tree_schema=None) -> GraphDiff:
    schema = resolve_tree_schema(node_tree, tree_schema=tree_schema)
    graph_tree_type = graph_def.tree_type
    target_tree_type = getattr(node_tree, "bl_idname", None) or getattr(schema, "tree_type", None)
    if graph_tree_type is not None and target_tree_type is not None and graph_tree_type != target_tree_type:
        raise ValueError(
            f"DSL tree type {graph_tree_type!r} does not match target tree type {target_tree_type!r}."
        )

    existing_graph = graph_from_node_tree(node_tree, tree_schema=schema)
    diff = compute_diff(existing_graph, graph_def)
    _prepare_group_interface(graph_def, diff, node_tree)
    apply_diff(diff, node_tree, schema)
    _finalize_group_interface(graph_def, node_tree)
    return diff


def apply_diff(diff: GraphDiff, node_tree, tree_schema) -> None:
    for edge in diff.links_to_remove:
        _remove_link(node_tree, edge)

    for node_id in diff.nodes_to_remove:
        node = find_node(node_tree, node_id)
        if node is not None:
            node_tree.nodes.remove(node)

    for node_def in diff.nodes_to_add:
        node = node_tree.nodes.new(node_def.type)
        node.name = node_def.id
        for property_name, value in sorted(node_def.properties.items()):
            _apply_assignment(node, property_name, value)

    _ensure_group_interface_sockets_from_diff(diff, node_tree)

    for change in diff.property_changes:
        node = find_node(node_tree, change.node_id)
        if node is None:
            raise ValueError(f"Node {change.node_id!r} is missing during graph apply.")
        node_schema = tree_schema.node_types[node.bl_idname]
        property_schema = node_schema.properties.get(change.property_name)
        if property_schema is not None:
            value = property_schema.default if change.clear else change.value
            _apply_assignment(node, change.property_name, value)
            continue
        if change.property_name in node_schema.inputs or _has_input_socket(node, change.property_name):
            socket = get_socket(node, change.property_name, is_output=False)
            if not hasattr(socket, "default_value"):
                raise ValueError(
                    f"Input socket {change.property_name!r} on node type {node.bl_idname} does not support default values."
                )
            if change.clear:
                continue
            socket.default_value = change.value
            continue
        raise ValueError(
            f"Property {change.property_name!r} is not valid on node type {node.bl_idname}."
        )

    for edge in diff.links_to_add:
        from_node = find_node(node_tree, edge.from_node)
        to_node = find_node(node_tree, edge.to_node)
        if from_node is None or to_node is None:
            raise ValueError("Cannot create a link for a node that does not exist.")
        output_socket = _resolve_socket_for_link(
            node_tree,
            node=from_node,
            socket_name=edge.from_socket,
            is_output=True,
            counterpart_node=to_node,
            counterpart_socket_name=edge.to_socket,
        )
        input_socket = _resolve_socket_for_link(
            node_tree,
            node=to_node,
            socket_name=edge.to_socket,
            is_output=False,
            counterpart_node=from_node,
            counterpart_socket_name=edge.from_socket,
        )
        node_tree.links.new(output_socket, input_socket)


def _remove_link(node_tree, edge) -> None:
    for link in list(node_tree.links):
        if (
            link.from_node.name == edge.from_node
            and link.from_socket.name == edge.from_socket
            and link.to_node.name == edge.to_node
            and link.to_socket.name == edge.to_socket
        ):
            node_tree.links.remove(link)


def _apply_assignment(node, assignment_name, value) -> None:
    if value is None:
        return
    if hasattr(node, assignment_name):
        setattr(node, assignment_name, value)
        return
    socket = get_socket(node, assignment_name, is_output=False)
    if not hasattr(socket, "default_value"):
        raise ValueError(
            f"Input socket {assignment_name!r} on node type {node.bl_idname} does not support default values."
        )
    socket.default_value = value


def _has_input_socket(node, socket_name: str) -> bool:
    sockets = getattr(node, "inputs", [])
    if hasattr(sockets, "get") and sockets.get(socket_name) is not None:
        return True
    return any(getattr(socket, "name", None) == socket_name for socket in sockets)


def _resolve_socket_for_link(node_tree, node, socket_name: str, is_output: bool, counterpart_node, counterpart_socket_name: str):
    try:
        return get_socket(node, socket_name, is_output=is_output)
    except ValueError:
        if not _can_create_group_interface_socket(node, is_output):
            raise

    direction = "INPUT" if is_output else "OUTPUT"
    counterpart_type = _infer_socket_type_from_node_socket(
        counterpart_node,
        counterpart_socket_name,
        is_output=not is_output,
    )
    if counterpart_type is None:
        raise ValueError(f"Socket {socket_name!r} was not found on node {node.name}.")

    _create_missing_group_interface_sockets(node_tree, {(direction, socket_name): counterpart_type})
    _refresh_group_interface(node_tree)
    refreshed_node = find_node(node_tree, node.name) or node
    return get_socket(refreshed_node, socket_name, is_output=is_output)


def _prepare_group_interface(graph_def: GraphDefinition, diff: GraphDiff, node_tree) -> None:
    requirements = _declared_group_interface_requirements(graph_def)
    inferred = _infer_group_interface_requirements(graph_def, node_tree)
    for key, value in inferred.items():
        requirements.setdefault(key, value)
    _create_missing_group_interface_sockets(node_tree, requirements)


def _ensure_group_interface_sockets(graph_def: GraphDefinition, node_tree) -> None:
    requirements = _declared_group_interface_requirements(graph_def)
    inferred = _infer_group_interface_requirements(graph_def, node_tree)
    for key, value in inferred.items():
        requirements.setdefault(key, value)
    _create_missing_group_interface_sockets(node_tree, requirements)


def _finalize_group_interface(graph_def: GraphDefinition, node_tree) -> None:
    declared = _declared_group_interface_requirements(graph_def)
    if not declared:
        return
    _synchronize_group_interface_sockets(node_tree, declared)


def _ensure_group_interface_sockets_from_diff(diff: GraphDiff, node_tree) -> None:
    node_defs = list(diff.nodes_to_add)
    for change in diff.property_changes:
        node = find_node(node_tree, change.node_id)
        if node is None:
            continue
        node_defs.append(type("_NodeDefLike", (), {"id": change.node_id, "type": node.bl_idname, "properties": {}})())

    graph_def = GraphDefinition(nodes=node_defs, edges=list(diff.links_to_add))
    requirements = _infer_group_interface_requirements(graph_def, node_tree)
    _create_missing_group_interface_sockets(node_tree, requirements)


def _infer_group_interface_requirements(graph_def: GraphDefinition, node_tree) -> dict[tuple[str, str], str]:
    nodes_by_id = graph_def.node_map()
    requirements: dict[tuple[str, str], str] = {}

    for edge in graph_def.edges:
        from_node = find_node(node_tree, edge.from_node) or nodes_by_id.get(edge.from_node)
        to_node = find_node(node_tree, edge.to_node) or nodes_by_id.get(edge.to_node)

        if getattr(from_node, "type", getattr(from_node, "bl_idname", None)) == "NodeGroupInput" and to_node is not None:
            socket_type = _infer_socket_type_from_node_socket(to_node, edge.to_socket, is_output=False)
            if socket_type is not None:
                requirements[("INPUT", edge.from_socket)] = socket_type

        if getattr(to_node, "type", getattr(to_node, "bl_idname", None)) == "NodeGroupOutput" and from_node is not None:
            socket_type = _infer_socket_type_from_node_socket(from_node, edge.from_socket, is_output=True)
            if socket_type is not None:
                requirements[("OUTPUT", edge.to_socket)] = socket_type

    return requirements


def _declared_group_interface_requirements(graph_def: GraphDefinition) -> dict[tuple[str, str], str]:
    requirements: dict[tuple[str, str], str] = {}
    for socket in graph_def.interface_sockets:
        requirements[(socket.direction, socket.name)] = socket.socket_type
    return requirements


def _can_create_group_interface_socket(node, is_output: bool) -> bool:
    node_type = getattr(node, "bl_idname", getattr(node, "type", None))
    return (is_output and node_type == "NodeGroupInput") or ((not is_output) and node_type == "NodeGroupOutput")


def _infer_socket_type_from_node_socket(node, socket_name: str, is_output: bool) -> str | None:
    try:
        socket = get_socket(node, socket_name, is_output=is_output)
    except ValueError:
        return None

    socket_type = getattr(socket, "bl_socket_idname", None)
    if socket_type:
        return socket_type
    socket_type = getattr(socket, "bl_idname", None)
    if socket_type:
        return socket_type
    return None


def _create_missing_group_interface_sockets(node_tree, requirements: dict[tuple[str, str], str]) -> None:
    if not _supports_group_interface(node_tree):
        return
    if not requirements:
        return

    existing = _collect_existing_group_interface_sockets(node_tree)
    for (direction, name), socket_type in requirements.items():
        if name in existing[direction]:
            continue
        _new_group_interface_socket(node_tree, name=name, direction=direction, socket_type=socket_type)
        existing[direction].add(name)
    _refresh_group_interface(node_tree)


def _synchronize_group_interface_sockets(node_tree, requirements: dict[tuple[str, str], str]) -> None:
    if not _supports_group_interface(node_tree):
        return

    existing_items = _collect_existing_group_interface_items(node_tree)
    for key, item in list(existing_items.items()):
        required_type = requirements.get(key)
        existing_type = _get_group_interface_socket_type(item)
        if required_type is None or (existing_type is not None and existing_type != required_type):
            _remove_group_interface_socket(node_tree, item, key[0])

    _create_missing_group_interface_sockets(node_tree, requirements)


def _collect_existing_group_interface_sockets(node_tree) -> dict[str, set[str]]:
    existing = {"INPUT": set(), "OUTPUT": set()}
    interface = getattr(node_tree, "interface", None)
    items = getattr(interface, "items_tree", ())
    for item in items:
        if getattr(item, "item_type", None) != "SOCKET":
            continue
        direction = getattr(item, "in_out", None)
        name = getattr(item, "name", None)
        if direction in existing and name:
            existing[direction].add(name)
    return existing


def _collect_existing_group_interface_items(node_tree) -> dict[tuple[str, str], object]:
    items_by_key: dict[tuple[str, str], object] = {}
    interface = getattr(node_tree, "interface", None)
    items = getattr(interface, "items_tree", None)
    if items is not None:
        for item in items:
            if getattr(item, "item_type", None) != "SOCKET":
                continue
            direction = getattr(item, "in_out", None)
            name = getattr(item, "name", None)
            if direction in {"INPUT", "OUTPUT"} and name:
                items_by_key[(direction, name)] = item
        return items_by_key

    for direction, collection_name in (("INPUT", "inputs"), ("OUTPUT", "outputs")):
        collection = getattr(node_tree, collection_name, None)
        if collection is None:
            continue
        for socket in collection:
            name = getattr(socket, "name", None)
            if name:
                items_by_key[(direction, name)] = socket
    return items_by_key


def _remove_group_interface_socket(node_tree, item, direction: str) -> None:
    interface = getattr(node_tree, "interface", None)
    if interface is not None and hasattr(interface, "remove"):
        interface.remove(item)
        return

    collection_name = "inputs" if direction == "INPUT" else "outputs"
    collection = getattr(node_tree, collection_name, None)
    if collection is not None and hasattr(collection, "remove"):
        collection.remove(item)
        return

    raise ValueError("Node tree does not support removing group interface sockets.")


def _get_group_interface_socket_type(item) -> str | None:
    for attribute in ("socket_type", "bl_socket_idname", "bl_idname"):
        value = getattr(item, attribute, None)
        if value:
            return value
    return None


def _supports_group_interface(node_tree) -> bool:
    return hasattr(node_tree, "interface") or hasattr(node_tree, "inputs") or hasattr(node_tree, "outputs")


def _refresh_group_interface(node_tree) -> None:
    interface_update = getattr(node_tree, "interface_update", None)
    if callable(interface_update):
        try:
            interface_update(None)
        except TypeError:
            try:
                interface_update()
            except TypeError:
                pass

    update = getattr(node_tree, "update", None)
    if callable(update):
        try:
            update()
        except TypeError:
            pass

    update_tag = getattr(node_tree, "update_tag", None)
    if callable(update_tag):
        try:
            update_tag()
        except TypeError:
            pass


def _new_group_interface_socket(node_tree, name: str, direction: str, socket_type: str) -> None:
    interface = getattr(node_tree, "interface", None)
    if interface is not None and hasattr(interface, "new_socket"):
        interface.new_socket(name=name, in_out=direction, socket_type=socket_type)
        return

    collection_name = "inputs" if direction == "INPUT" else "outputs"
    collection = getattr(node_tree, collection_name, None)
    if collection is not None and hasattr(collection, "new"):
        collection.new(socket_type, name)
        return

    raise ValueError("Node tree does not support creating group interface sockets.")
