from agentfw.core.models import AgentDefinition
from agentfw.core.state import AgentState, ExecutionContext


def _ctx(variables: dict[str, object]) -> ExecutionContext:
    definition = AgentDefinition(
        name="dummy",
        description=None,
        input_schema=None,
        output_schema=None,
        steps={},
        entry_step_id="",
        end_step_ids=set(),
        serialize_enabled=False,
        serialize_base_dir=None,
        serialize_per_step=False,
    )
    state = AgentState(
        run_id="r1",
        agent_name="dummy",
        current_step_id=None,
        finished=False,
        failed=False,
        variables=dict(variables),
        history=[],
        retry_counts={},
    )
    return ExecutionContext(definition=definition, state=state, engine=None)  # type: ignore[arg-type]


def test_template_keeps_literal_braces() -> None:
    ctx = _ctx({})
    template = '{"a": 1}'
    assert ctx.resolve_template(template) == template


def test_template_substitutes_known_variable() -> None:
    ctx = _ctx({"task_text": "hello"})
    assert ctx.resolve_template("TASK: {task_text}") == "TASK: hello"


def test_template_leaves_missing_variable() -> None:
    ctx = _ctx({})
    assert ctx.resolve_template("X={missing}") == "X={missing}"
