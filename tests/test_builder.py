from __future__ import annotations

import pathlib
import sys
import unittest
import uuid

from langchain_community.graphs import Neo4jGraph

from langchain_core.documents import Document
from langchain_community.graphs.graph_document import GraphDocument, Node, Relationship

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from graph_tool.builder import KnowledgeGraphBuilder
from graph_tool.config import GraphSettings


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


def _make_doc(metadata: dict | None = None) -> Document:
    return Document(page_content="", metadata=metadata or {})


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

    def test_raw_text_entry_node_and_mentions(self) -> None:
        fake_graph = FakeGraph()
        builder = KnowledgeGraphBuilder(graph=fake_graph, llm=None)

        metadata = {
            "entry_id": "entry-123",
            "timestamp": "2024-01-01T00:00:00Z",
            "source": "tester",
        }
        doc = Document(page_content="Some raw text", metadata=metadata)

        node = Node(id="alice", type="Person", properties={})
        graph_document = GraphDocument(nodes=[node], relationships=[], source=doc)

        builder._merge_graph_documents([graph_document])

        merge_entry_queries = [
            (statement, params)
            for statement, params in fake_graph.queries
            if "MERGE (e:RawText" in statement
        ]
        self.assertTrue(merge_entry_queries, "Raw text entry was not merged")
        entry_params = merge_entry_queries[0][1]
        self.assertEqual(entry_params["id"], "entry-123")
        self.assertEqual(entry_params["props"]["source"], "tester")
        self.assertEqual(entry_params["props"]["timestamp"], "2024-01-01T00:00:00Z")
        self.assertEqual(entry_params["props"]["text"], "Some raw text")

        mention_queries = [
            (statement, params)
            for statement, params in fake_graph.queries
            if "MERGE (e)-[:MENTIONS]->(n)" in statement
        ]
        self.assertTrue(mention_queries, "Mention relationship to entities was not created")
        self.assertEqual(mention_queries[0][1]["entry_id"], "entry-123")
        self.assertEqual(mention_queries[0][1]["node_id"], "alice")


class KnowledgeGraphBuilderIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        settings = GraphSettings()
        cls.neo4j_url = settings.neo4j_url
        try:
            cls.graph = Neo4jGraph(**settings.neo4j_kwargs())
            cls.graph.query("RETURN 1 AS ok")
        except Exception as exc:  # pragma: no cover - defensive skip when Neo4j unavailable
            raise unittest.SkipTest(
                f"Neo4j not reachable at {settings.neo4j_url}: {exc}"
            )

    def setUp(self) -> None:
        self.run_id = f"test-run-{uuid.uuid4()}"

    def tearDown(self) -> None:  # pragma: no cover - cleanup best effort
        try:
            self.graph.query(
                "MATCH (n {run_id: $run_id}) DETACH DELETE n", {"run_id": self.run_id}
            )
        except Exception:
            pass

    def test_relationship_persists_in_real_neo4j(self) -> None:
        builder = KnowledgeGraphBuilder(graph=self.graph, llm=None)

        ghost_id = f"ghost-{self.run_id}"
        target_id = f"target-{self.run_id}"
        entry_id = f"entry-{self.run_id}"

        ghost = Node(id="", type="Ghost", properties={"id": ghost_id, "run_id": self.run_id})
        target = Node(id="", type="Person", properties={"id": target_id, "run_id": self.run_id})
        rel = Relationship(
            source=ghost,
            target=target,
            type="haunts",
            properties={"run_id": self.run_id},
        )

        graph_document = GraphDocument(
            nodes=[ghost, target],
            relationships=[rel],
            source=_make_doc(
                {
                    "run_id": self.run_id,
                    "entry_id": entry_id,
                    "timestamp": "2024-01-01T00:00:00Z",
                    "source": "integration-test",
                }
            ),
        )

        builder._merge_graph_documents([graph_document])

        result = self.graph.query(
            (
                "MATCH (a {id: $a_id, run_id: $run_id})-"
                "[r:`haunts` {run_id: $run_id}]->(b {id: $b_id, run_id: $run_id})"
                " RETURN r"
            ),
            {"a_id": ghost_id, "b_id": target_id, "run_id": self.run_id},
        )

        self.assertTrue(
            result,
            "\n".join(
                [
                    "Relationship was not found in the target Neo4j instance.",
                    f"Neo4j URL: {self.neo4j_url}",
                    "Check that APOC is installed and that the configured credentials"
                    " can create nodes and relationships.",
                ]
            ),
        )

        entry = self.graph.query(
            "MATCH (e:RawText {id: $entry_id, run_id: $run_id}) RETURN e",
            {"entry_id": entry_id, "run_id": self.run_id},
        )
        self.assertTrue(entry, "Raw text entry node was not persisted in Neo4j")

        mentions = self.graph.query(
            (
                "MATCH (e:RawText {id: $entry_id, run_id: $run_id})-"
                "[:MENTIONS]->(n {id: $node_id, run_id: $run_id}) RETURN n"
            ),
            {"entry_id": entry_id, "node_id": ghost_id, "run_id": self.run_id},
        )
        self.assertTrue(mentions, "Mention relationship between entry and entity was not created")
