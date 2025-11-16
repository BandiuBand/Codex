from __future__ import annotations

import json
import logging
import random
import threading
from dataclasses import dataclass, field
from typing import Any

from langchain_community.chat_models import ChatOllama
from langchain_community.graphs import Neo4jGraph

logger = logging.getLogger(__name__)


@dataclass
class GraphVerifier:
    """Runs periodic graph health checks and enrichment."""

    graph: Neo4jGraph
    llm: ChatOllama
    interval_seconds: int = 900
    max_relationship_suggestions: int = 5
    _timer: threading.Timer | None = field(default=None, init=False, repr=False)

    def start(self) -> None:
        """Begin periodic verification."""

        if self._timer:
            logger.info("Graph verifier already running.")
            return
        logger.info("Starting graph verifier every %s seconds", self.interval_seconds)
        self._schedule_next()

    def stop(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None
            logger.info("Graph verifier stopped.")

    def _schedule_next(self) -> None:
        self._timer = threading.Timer(self.interval_seconds, self._run_cycle)
        self._timer.daemon = True
        self._timer.start()

    def _run_cycle(self) -> None:
        try:
            logger.info("Running graph verification cycle...")
            self.verify_and_enrich()
        finally:
            # Schedule the next run regardless of errors to keep the loop alive.
            self._schedule_next()

    def verify_and_enrich(self) -> None:
        """Run a collection of sanity checks and enrichment passes."""

        orphaned = self._find_orphan_nodes(limit=25)
        if orphaned:
            logger.warning("Found %d orphaned node(s) with no relationships", len(orphaned))

        duplicates = self._find_duplicates()
        if duplicates:
            logger.warning("Found %d possible duplicate names", len(duplicates))

        candidates = self._sample_nodes_for_enrichment(limit=10)
        if candidates:
            suggestions = self._suggest_relationships(candidates)
            if suggestions:
                self._apply_relationship_suggestions(suggestions)

    def _find_orphan_nodes(self, limit: int = 25) -> list[dict[str, Any]]:
        query = "MATCH (n) WHERE NOT (n)--() RETURN n.name AS name, labels(n) AS labels LIMIT $limit"
        return self.graph.query(query, params={"limit": limit})

    def _find_duplicates(self) -> list[dict[str, Any]]:
        query = (
            "MATCH (n) WHERE exists(n.name) "
            "WITH toLower(n.name) AS name, collect(DISTINCT labels(n)) AS labels, count(*) AS cnt "
            "WHERE cnt > 1 RETURN name, labels, cnt"
        )
        return self.graph.query(query)

    def _sample_nodes_for_enrichment(self, limit: int = 10) -> list[dict[str, Any]]:
        results = self.graph.query(
            "MATCH (n) RETURN n.name AS name, labels(n) AS labels, n.description AS description LIMIT $limit",
            params={"limit": limit * 2},
        )
        random.shuffle(results)
        return results[:limit]

    def _suggest_relationships(self, nodes: list[dict[str, Any]]) -> list[dict[str, str]]:
        """Ask the LLM to propose edges between sampled nodes."""

        if len(nodes) < 2:
            return []

        prompt = self._format_relationship_prompt(nodes)
        response = self.llm.invoke(prompt)
        try:
            text = response.content if hasattr(response, "content") else str(response)
            data = json.loads(self._extract_json_block(text))
            if not isinstance(data, list):
                return []
            cleaned: list[dict[str, str]] = []
            for item in data[: self.max_relationship_suggestions]:
                if not {"source", "target", "relationship"} <= set(item):
                    continue
                cleaned.append(
                    {
                        "source": item["source"],
                        "target": item["target"],
                        "relationship": item["relationship"],
                    }
                )
            return cleaned
        except json.JSONDecodeError as exc:
            logger.debug("Could not parse relationship suggestions: %s", exc)
        return []

    def _format_relationship_prompt(self, nodes: list[dict[str, Any]]) -> str:
        description_lines = []
        for node in nodes:
            description_lines.append(
                " - Name: {name}; Labels: {labels}; Description: {desc}".format(
                    name=node.get("name", ""),
                    labels=", ".join(node.get("labels", [])),
                    desc=node.get("description") or "",
                )
            )

        return (
            "You are verifying a knowledge graph. Here are node summaries:\n"
            + "\n".join(description_lines)
            + "\nSuggest up to {max_rel} missing relationships as a JSON array. "
            "Each item must have 'source', 'target', and 'relationship' fields. "
            "Only suggest relationships that are strongly implied by the descriptions."
        ).format(max_rel=self.max_relationship_suggestions)

    def _extract_json_block(self, text: str) -> str:
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]
        return text

    def _apply_relationship_suggestions(self, suggestions: list[dict[str, str]]) -> None:
        if not suggestions:
            return

        for suggestion in suggestions:
            self.graph.query(
                (
                    "MATCH (a {name: $source}), (b {name: $target}) "
                    "MERGE (a)-[r:`{rel}`]->(b) RETURN a,b,r"
                ).format(rel=suggestion["relationship"]),
                params={
                    "source": suggestion["source"],
                    "target": suggestion["target"],
                },
            )
            logger.info(
                "Applied suggested relationship %s -[%s]-> %s",
                suggestion["source"],
                suggestion["relationship"],
                suggestion["target"],
            )
