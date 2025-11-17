from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Mapping

from langchain_core.documents import Document
from langchain_community.chat_models import ChatOllama
from langchain_community.graphs import Neo4jGraph
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_community.graphs.graph_document import (
    GraphDocument,
    Node,
    Relationship,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import GraphSettings

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeGraphBuilder:
    """Converts free-form text into a Neo4j knowledge graph."""

    graph: Neo4jGraph
    llm: ChatOllama
    chunk_size: int = 1200
    chunk_overlap: int = 200

    @classmethod
    def from_settings(cls, settings: GraphSettings) -> "KnowledgeGraphBuilder":
        graph = Neo4jGraph(**settings.neo4j_kwargs())
        llm = ChatOllama(model=settings.ollama_model, temperature=settings.llm_temperature)
        return cls(
            graph=graph,
            llm=llm,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

    def _split_into_documents(
        self, text: str, metadata: Mapping | None = None
    ) -> list[Document]:
        """Split long text into overlapping windows ready for LLM ingestion."""

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap
        )
        chunks = splitter.split_text(text)
        docs: list[Document] = []
        base_metadata = metadata or {}
        for idx, chunk in enumerate(chunks):
            docs.append(
                Document(
                    page_content=chunk,
                    metadata={**base_metadata, "chunk": idx, "total_chunks": len(chunks)},
                )
            )
        return docs

    def _extract_graph_documents(self, documents: Iterable[Document]) -> list[GraphDocument]:
        transformer = LLMGraphTransformer(llm=self.llm)
        return transformer.convert_to_graph_documents(list(documents))

    def _merge_graph_documents(self, graph_documents: list[GraphDocument]) -> None:
        """Merge nodes/relationships into Neo4j to avoid duplicates."""

        def _resolve_node_id(node: Node) -> str | None:
            """Return a stable identifier for a Node object."""

            properties = node.properties or {}
            raw_id = node.id or properties.get("id") or properties.get("name")
            return str(raw_id) if raw_id is not None else None

        def _normalize_rel_type(rel_type: str | Iterable[str] | None) -> str:
            """Return a Neo4j-safe relationship type name."""

            if isinstance(rel_type, str):
                rel_type = rel_type.strip()
                return rel_type.replace(":", "_").replace(" ", "_") or "RELATED_TO"

            try:
                first_type = next((t for t in rel_type if t), None)
            except TypeError:
                first_type = None

            if not first_type:
                return "RELATED_TO"

            return str(first_type).replace(":", "_").replace(" ", "_")

        def _merge_node(node: Node, known_ids: set[str]) -> str | None:
            """Merge a single node and return its identifier."""

            properties = node.properties or {}
            node_id = _resolve_node_id(node)
            if not node_id:
                logger.debug("Skipping node without identifier: %s", node)
                return None

            labels = [node.type] if isinstance(node.type, str) else list(node.type)
            label_clause = ":" + ":".join(labels) if labels else ""
            if "name" not in properties:
                properties["name"] = node_id
            # Persist the resolved identifier and merged properties on the node so
            # downstream relationship handling can reliably find endpoints even
            # when the original `id` field was empty.
            node.id = node_id
            node.properties = properties
            self.graph.query(
                f"MERGE (n{label_clause} {{id: $id}}) SET n += $props RETURN n",
                params={"id": node_id, "props": properties},
            )
            known_ids.add(node_id)
            return node_id

        for graph_doc in graph_documents:
            known_ids: set[str] = set()

            for node in graph_doc.nodes:
                _merge_node(node, known_ids)

            for rel in graph_doc.relationships:
                if not rel.source or not rel.target:
                    logger.debug("Skipping relationship missing endpoints: %s", rel)
                    continue

                source_id = (
                    _resolve_node_id(rel.source) if isinstance(rel.source, Node) else rel.source
                )
                target_id = (
                    _resolve_node_id(rel.target) if isinstance(rel.target, Node) else rel.target
                )

                if isinstance(rel.source, Node) and source_id and source_id not in known_ids:
                    source_id = _merge_node(rel.source, known_ids)
                if isinstance(rel.target, Node) and target_id and target_id not in known_ids:
                    target_id = _merge_node(rel.target, known_ids)

                if not source_id or not target_id:
                    logger.debug(
                        "Skipping relationship with unresolved endpoints: %s", rel
                    )
                    continue

                rel_type = _normalize_rel_type(rel.type)
                self.graph.query(
                    (
                        "MATCH (a {id: $source_id}) MATCH (b {id: $target_id}) "
                        f"MERGE (a)-[r:`{rel_type}`]->(b) SET r += $props RETURN r"
                    ),
                    params={
                        "source_id": source_id,
                        "target_id": target_id,
                        "props": rel.properties or {},
                    },
                )

    def ingest_text(self, text: str, metadata: Mapping | None = None) -> None:
        """Create graph objects from text and push them to Neo4j."""

        if not text.strip():
            logger.info("No content to ingest; skipping.")
            return

        docs = self._split_into_documents(text, metadata)
        logger.info("Extracting graph from %d document chunk(s)...", len(docs))
        graph_documents = self._extract_graph_documents(docs)
        if not graph_documents:
            logger.warning("LLM did not return any graph content.")
            return
        nodes_count = sum(len(doc.nodes) for doc in graph_documents)
        rels_count = sum(len(doc.relationships) for doc in graph_documents)
        logger.info(
            "Merging graph with %d nodes and %d relationships.",
            nodes_count,
            rels_count,
        )
        self._merge_graph_documents(graph_documents)

    def ingest_documents(self, documents: Iterable[Document]) -> None:
        graph_documents = self._extract_graph_documents(list(documents))
        self._merge_graph_documents(graph_documents)
