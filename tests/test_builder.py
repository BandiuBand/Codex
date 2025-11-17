from __future__ import annotations

import pathlib
import sys
import unittest

from langchain_core.documents import Document
from langchain_community.graphs.graph_document import GraphDocument, Node, Relationship

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from graph_tool.builder import KnowledgeGraphBuilder


class FakeGraph:
    def __init__(self) -> None:
        self.queries: list[tuple[str, dict]] = []

    def query(self, statement: str, params: dict | None = None):  # pragma: no cover - simple test double
        self.queries.append((statement, params or {}))
        return []

    def snapshot(self) -> str:  # pragma: no cover - debug aid only
        lines = ["Captured queries:"]
        if not self.queries:
            lines.append("  (none)")
            return "\n".join(lines)

        for idx, (statement, params) in enumerate(self.queries, start=1):
            lines.append(f"  {idx}. {statement}")
            if params:
                lines.append(f"     params: {params}")
        return "\n".join(lines)


def _make_doc() -> Document:
    return Document(page_content="", metadata={})


def _debug_context(graph: FakeGraph, nodes: list[Node], relationships: list[Relationship]):  # pragma: no cover - debug aid only
    def _printer():
        print("\n==== Debug snapshot ====")
        print(graph.snapshot())
        print("Nodes:")
        for node in nodes:
            print(f"  {node.type} id={node.id!r} properties={node.properties}")
        print("Relationships:")
        for rel in relationships:
            print(
                "  "
                f"{rel.source.id!r} -[{rel.type}]-> {rel.target.id!r}"
                f" properties={rel.properties}"
            )
        print("========================\n")

    return _printer


class KnowledgeGraphBuilderTests(unittest.TestCase):
    def test_relationships_are_merged_when_nodes_present(self) -> None:
        fake_graph = FakeGraph()
        builder = KnowledgeGraphBuilder(graph=fake_graph, llm=None)

        alice = Node(id="alice", type="Person", properties={})
        bob = Node(id="bob", type="Person", properties={})
        rel = Relationship(source=alice, target=bob, type="knows", properties={"since": 2020})

        self.addCleanup(_debug_context(fake_graph, [alice, bob], [rel]))

        graph_document = GraphDocument(nodes=[alice, bob], relationships=[rel], source=_make_doc())

        builder._merge_graph_documents([graph_document])

        self.assertTrue(
            any("MERGE (a)-[r:`knows`]->(b)" in statement for statement, _ in fake_graph.queries)
        )

    def test_node_identifier_can_come_from_properties_id(self) -> None:
        fake_graph = FakeGraph()
        builder = KnowledgeGraphBuilder(graph=fake_graph, llm=None)

        ghost = Node(id="", type="Ghost", properties={"id": "ghost-1"})
        target = Node(id="target", type="Person", properties={})
        rel = Relationship(source=ghost, target=target, type="haunts", properties={})

        self.addCleanup(_debug_context(fake_graph, [ghost, target], [rel]))

        graph_document = GraphDocument(nodes=[ghost, target], relationships=[rel], source=_make_doc())

        builder._merge_graph_documents([graph_document])

        relationship_params = [
            params
            for statement, params in fake_graph.queries
            if "MERGE (a)-[r:`haunts`]->(b)" in statement
        ]

        self.assertTrue(
            relationship_params,
            "\n".join(
                [
                    "Relationship merge query was not executed.",
                    fake_graph.snapshot(),
                    f"Source node after merge: id={ghost.id!r} properties={ghost.properties}",
                ]
            ),
        )
        self.assertEqual(
            relationship_params[0]["source_id"],
            "ghost-1",
            "\n".join(
                [
                    "Unexpected relationship source id.",
                    fake_graph.snapshot(),
                    f"Source node after merge: id={ghost.id!r} properties={ghost.properties}",
                ]
            ),
        )

    def test_node_id_is_persisted_after_merge(self) -> None:
        fake_graph = FakeGraph()
        builder = KnowledgeGraphBuilder(graph=fake_graph, llm=None)

        unnamed = Node(id="", type="Entity", properties={"name": "ghosty"})
        target = Node(id="target", type="Person", properties={})
        rel = Relationship(source=unnamed, target=target, type="knows", properties={})

        self.addCleanup(_debug_context(fake_graph, [unnamed, target], [rel]))

        graph_document = GraphDocument(nodes=[unnamed, target], relationships=[rel], source=_make_doc())

        builder._merge_graph_documents([graph_document])

        self.assertEqual(unnamed.id, "ghosty")
        relationship_params = [
            params
            for statement, params in fake_graph.queries
            if "MERGE (a)-[r:`knows`]->(b)" in statement
        ]
        self.assertTrue(relationship_params, "Relationship merge query was not executed")
        self.assertEqual(relationship_params[0]["source_id"], "ghosty")
