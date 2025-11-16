from __future__ import annotations

import argparse
import logging
import sys
import threading
from pathlib import Path

from .builder import KnowledgeGraphBuilder
from .config import GraphSettings
from .verifier import GraphVerifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest text into Neo4j via LangChain/Ollama and run background verification.",
    )
    parser.add_argument("--text", help="Raw text to ingest into the knowledge graph.")
    parser.add_argument("--input-file", type=Path, help="Path to a file containing text to ingest.")
    parser.add_argument(
        "--start-verifier",
        action="store_true",
        help="Keep running and periodically verify/enrich the graph.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Override the verification interval in seconds.",
    )
    return parser.parse_args(argv)


def load_input_text(args: argparse.Namespace) -> str:
    if args.text:
        return args.text
    if args.input_file and args.input_file.exists():
        return args.input_file.read_text(encoding="utf-8")
    raise SystemExit("Either --text or --input-file is required")


def main(argv: list[str] | None = None) -> None:
    argv = argv or sys.argv[1:]
    args = parse_args(argv)
    settings = GraphSettings()

    if args.interval:
        settings.verification_interval_seconds = args.interval

    text = load_input_text(args)

    builder = KnowledgeGraphBuilder.from_settings(settings)
    builder.ingest_text(text, metadata={"source": str(args.input_file) if args.input_file else "cli"})
    logger.info("Ingestion complete.")

    if args.start_verifier:
        verifier = GraphVerifier(
            graph=builder.graph,
            llm=builder.llm,
            interval_seconds=settings.verification_interval_seconds,
            max_relationship_suggestions=settings.max_relationship_suggestions,
        )
        verifier.start()
        logger.info("Verifier is running in the background. Press Ctrl+C to stop.")
        try:
            while True:
                # Sleep forever; timer thread will do the work.
                threading.Event().wait(3600)
        except KeyboardInterrupt:
            verifier.stop()


if __name__ == "__main__":
    main()
