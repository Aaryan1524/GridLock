"""Project relationship graph (handoff section 13): projects are nodes, relationships are edges."""

from __future__ import annotations

import networkx as nx

from gridlock.models.domain import Project, Relationship


class GraphError(ValueError):
    """Raised when an edge would break the cross-utility requirement (I-8)."""


def build_graph(projects: list[Project], relationships: list[Relationship]) -> nx.Graph:
    """Every project is a node, located or not; an edge exists only for a cross-utility relationship."""
    graph = nx.Graph()
    for project in sorted(projects, key=lambda item: item.id):
        graph.add_node(project.id, utility=project.utility, located=project.geometry is not None)
    for relationship in sorted(relationships, key=lambda item: item.id):
        a, b = relationship.project_a, relationship.project_b
        if a not in graph or b not in graph:
            raise GraphError(f"{relationship.id} refers to a project that is not in the dataset")
        if graph.nodes[a]["utility"] == graph.nodes[b]["utility"]:
            raise GraphError(f"{relationship.id} joins two {graph.nodes[a]['utility']} projects (I-8)")
        graph.add_edge(a, b, relationship=relationship)
    return graph


def components(graph: nx.Graph) -> list[list[str]]:
    """Connected components with at least one edge, each sorted, in a stable order."""
    groups = [sorted(group) for group in nx.connected_components(graph) if len(group) > 1]
    return sorted(groups, key=lambda group: group[0])
