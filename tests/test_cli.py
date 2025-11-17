from __future__ import annotations

import builtins
import pathlib
import sys
import unittest
from unittest import mock

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from graph_tool import cli


class ConsoleModeTests(unittest.TestCase):
    def test_console_mode_ingests_user_input(self) -> None:
        builder = mock.Mock()
        builder.ingest_text = mock.Mock()

        with mock.patch.object(cli, "KnowledgeGraphBuilder") as builder_cls:
            builder_cls.from_settings.return_value = builder
            with mock.patch.object(builtins, "input", side_effect=["hello world", "tester", ""]):
                cli.run_console_mode(cli.GraphSettings(), start_verifier=False)

        builder.ingest_text.assert_called_once_with(
            "hello world", metadata={"source": "tester"}
        )


if __name__ == "__main__":
    unittest.main()
