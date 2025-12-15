from dataclasses import dataclass

from agentfw.core.models import AgentDefinition
from agentfw.core.state import AgentState, ExecutionContext
from agentfw.llm.base import DummyLLMClient
from agentfw.tools.builtin import LLMTool


@dataclass
class NoOpEngine:
    pass


def make_context(variables: dict[str, object]) -> ExecutionContext:
    state = AgentState(run_id="r1", agent_name="agent", variables=variables)
    definition = AgentDefinition(name="agent")
    return ExecutionContext(definition=definition, state=state, engine=NoOpEngine())


def test_llm_tool_parses_json_when_enabled() -> None:
    client = DummyLLMClient(prefix="")
    tool = LLMTool(client=client)

    ctx = make_context({"x": 1})
    result = tool.execute(
        ctx,
        {
            "prompt": "{x}",
            "parse_json": True,
        },
    )

    assert result["prompt"] == "1"
    assert result["output_text"] == "1"
    assert result.get("parsed_json") == 1
    assert "json_error" not in result


def test_llm_tool_reports_json_error_without_throwing() -> None:
    client = DummyLLMClient(prefix="not json: ")
    tool = LLMTool(client=client)

    ctx = make_context({})
    result = tool.execute(ctx, {"prompt": "hello", "parse_json": True})

    assert result["parsed_json"] is None
    assert "json_error" in result
