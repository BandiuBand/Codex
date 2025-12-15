from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def run_demo() -> None:
    """Execute the bundled simple agent demo."""
    from demo.simple_agent_demo import main as demo_main

    demo_main()


def run_web(host: str, port: int) -> None:
    """Start the web graph editor server."""
    from agentfw.web.server import run_server

    run_server(host=host, port=port)


def run_tests(pytest_args: list[str] | None = None) -> int:
    """Execute the backend + frontend integration tests."""

    cmd = [sys.executable, "-m", "pytest"]
    if pytest_args:
        cmd.extend(pytest_args)

    completed = subprocess.run(cmd, check=False)
    return completed.returncode


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Unified entry point for the web editor, demo suite, and tests.",
    )
    subparsers = parser.add_subparsers(dest="command", required=False)

    web_parser = subparsers.add_parser("web", help="Run the web graph editor server")
    web_parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    web_parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")

    subparsers.add_parser("demo", help="Run the simple agent demo suite")

    subparsers.add_parser("test", help="Run backend and frontend integration tests")

    args, unknown = parser.parse_known_args()

    if args.command == "demo":
        run_demo()
    elif args.command == "test":
        raise SystemExit(run_tests(pytest_args=unknown))
    else:
        if unknown:
            parser.error(f"unrecognized arguments: {' '.join(unknown)}")
        # Default to web to make `python run.py` immediately useful.
        host = getattr(args, "host", "127.0.0.1")
        port = getattr(args, "port", 8000)
        run_web(host=host, port=port)


if __name__ == "__main__":
    main()
