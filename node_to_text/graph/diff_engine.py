"""Compute minimal graph updates between two graph definitions."""

from __future__ import annotations

from node_to_text.models import EdgeDef, GraphDefinition, GraphDiff, PropertyChange


def compute_diff(existing_graph: GraphDefinition, new_graph: GraphDefinition) -> GraphDiff:
    existing_nodes = existing_graph.node_map()
    new_nodes = new_graph.node_map()

    existing_ids = set(existing_nodes)
    new_ids = set(new_nodes)
    replaced_ids = {
        node_id
        for node_id in existing_ids & new_ids
        if existing_nodes[node_id].type != new_nodes[node_id].type
    }

    nodes_to_remove = sorted((existing_ids - new_ids) | replaced_ids)
    nodes_to_add = sorted(
        [new_nodes[node_id] for node_id in (new_ids - existing_ids) | replaced_ids],
        key=lambda node: node.id,
    )

    property_changes: list[PropertyChange] = []
    for node_id in sorted((existing_ids & new_ids) - replaced_ids):
        existing_node = existing_nodes[node_id]
        new_node = new_nodes[node_id]
        property_names = set(existing_node.properties) | set(new_node.properties)
        for property_name in sorted(property_names):
            if property_name not in new_node.properties:
                property_changes.append(
                    PropertyChange(node_id=node_id, property_name=property_name, clear=True)
                )
                continue
            if existing_node.properties.get(property_name) != new_node.properties[property_name]:
                property_changes.append(
                    PropertyChange(
                        node_id=node_id,
                        property_name=property_name,
                        value=new_node.properties[property_name],
                    )
                )

    existing_edges = existing_graph.edge_map()
    new_edges = new_graph.edge_map()
    replaced_existing_edges = {
        key: edge
        for key, edge in existing_edges.items()
        if edge.from_node in replaced_ids or edge.to_node in replaced_ids
    }
    replaced_new_edges = {
        key: edge
        for key, edge in new_edges.items()
        if edge.from_node in replaced_ids or edge.to_node in replaced_ids
    }

    links_to_remove = sorted(
        [
            existing_edges[key]
            for key in (set(existing_edges) - set(new_edges)) | set(replaced_existing_edges)
        ],
        key=lambda edge: edge.key(),
    )
    links_to_add = sorted(
        [new_edges[key] for key in (set(new_edges) - set(existing_edges)) | set(replaced_new_edges)],
        key=lambda edge: edge.key(),
    )

    return GraphDiff(
        nodes_to_add=nodes_to_add,
        nodes_to_remove=nodes_to_remove,
        property_changes=property_changes,
        links_to_add=links_to_add,
        links_to_remove=links_to_remove,
    )
