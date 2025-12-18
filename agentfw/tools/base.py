"""Legacy BaseTool stub.

Використовуйте atomic агенти та ExecutionEngine замість старих Tool.*
"""

class BaseTool:  # pragma: no cover - legacy stub
    def __init__(self, *args, **kwargs):
        raise RuntimeError("Legacy removed; use AgentSpec/engine")

    def run(self, variables):  # noqa: ANN001
        raise RuntimeError("Legacy removed; use AgentSpec/engine")
