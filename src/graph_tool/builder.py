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
            return node.id or properties.get("name")

        for graph_doc in graph_documents:
            node_ids: dict[int, str] = {}

            for node in graph_doc.nodes:
                properties = node.properties or {}
                node_id = _resolve_node_id(node)
                if not node_id:
                    logger.debug("Skipping node without identifier: %s", node)
                    continue

                node_ids[id(node)] = node_id

                labels = [node.type] if isinstance(node.type, str) else list(node.type)
                label_clause = ":" + ":".join(labels) if labels else ""
                if "name" not in properties:
                    properties["name"] = node_id
                self.graph.query(
                    f"MERGE (n{label_clause} {{id: $id}}) SET n += $props RETURN n",
                    params={"id": node_id, "props": properties},
                )

            for rel in graph_doc.relationships:
                if not rel.source or not rel.target:
                    logger.debug("Skipping relationship missing endpoints: %s", rel)
                    continue

                source_id = (
                    node_ids.get(id(rel.source))
                    if isinstance(rel.source, Node)
                    else rel.source
                )
                target_id = (
                    node_ids.get(id(rel.target))
                    if isinstance(rel.target, Node)
                    else rel.target
                )

                if not source_id or not target_id:
                    logger.debug(
                        "Skipping relationship with unresolved endpoints: %s", rel
                    )
                    continue

                rel_type = rel.type if isinstance(rel.type, str) else ":".join(rel.type)
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
