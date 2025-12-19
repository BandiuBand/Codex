from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def run_demo() -> None:
    """Execute the bundled simple agent demo."""
    logger.info("Starting demo workflow")
    from demo.simple_agent_demo import main as demo_main

    try:
        demo_main()
    except Exception:  # noqa: BLE001
        logger.exception("Demo workflow failed")
        raise
    logger.info("Demo workflow completed successfully")


def run_web(host: str, port: int) -> None:
    """Start the web graph editor server."""
    logger.info("Starting web editor", extra={"host": host, "port": port})
    from agentfw.web.server import run_server

    try:
        run_server(host=host, port=port)
    except Exception:  # noqa: BLE001
        logger.exception("Web editor server failed to start")
        raise


def run_tests(pytest_args: list[str] | None = None) -> int:
    """Execute the backend + frontend integration tests."""

    cmd = [sys.executable, "-m", "pytest"]
    if pytest_args:
        cmd.extend(pytest_args)

    logger.info("Running test suite", extra={"cmd": cmd})
    completed = subprocess.run(cmd, check=False)
    if completed.returncode == 0:
        logger.info("Tests finished successfully")
    else:
        logger.error("Tests failed", extra={"return_code": completed.returncode})
    return completed.returncode


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Unified entry point: start the web server, run the demo, or execute tests.",
    )
    subparsers = parser.add_subparsers(dest="command", required=False)

    web_parser = subparsers.add_parser("web", help="Run the web graph editor server")
    web_parser.add_argument("--host", default="127.0.0.2", help="Host to bind (default: 127.0.0.2)")
    web_parser.add_argument("--port", type=int, default=8002, help="Port to bind (default: 8002)")

    subparsers.add_parser("demo", help="Run the simple agent demo suite")

    subparsers.add_parser("test", help="Run backend and frontend integration tests")

    args, unknown = parser.parse_known_args()

    logger.info("Parsed command", extra={"command": args.command})
    if args.command == "demo":
        run_demo()
    elif args.command == "test":
        raise SystemExit(run_tests(pytest_args=unknown))
    elif args.command == "web" or args.command is None:
        if unknown:
            parser.error(f"unrecognized arguments: {' '.join(unknown)}")
        host = getattr(args, "host", "127.0.0.2")
        port = getattr(args, "port", 8002)
        run_web(host=host, port=port)
    else:
        parser.error(f"unrecognized command: {args.command}")


if __name__ == "__main__":
    main()
