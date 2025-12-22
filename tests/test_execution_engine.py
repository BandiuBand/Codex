from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from agentfw.core.agent_spec import (
    AgentItemSpec,
    AgentSpec,
    BindingSpec,
    GraphSpec,
    LaneSpec,
    LocalVarSpec,
    UiPlacementSpec,
    VarSpec,
    WhenSpec,
    STOP_FLAG_VAR,
)
from agentfw.io.agent_yaml import save_agent_spec
from agentfw.llm.base import LLMClient
from agentfw.runtime.engine import AgentRepository, ExecutionEngine


def _save_atomic(tmp_path, name: str, code: str, output_name: str) -> None:
    spec = AgentSpec(
        name=name,
        title_ua=name,
        description_ua=None,
        kind="atomic",
        executor="python",
        inputs=[VarSpec(name=output_name)],
        locals=[LocalVarSpec(name="code", value=code)],
        outputs=[VarSpec(name=output_name)],
    )
    save_agent_spec(tmp_path / f"{name}.yaml", spec)


def test_agent_spec_initializes_stop_flag(tmp_path) -> None:
    spec = AgentSpec(
        name="auto_stop",
        title_ua="auto_stop",
        description_ua=None,
        kind="atomic",
        executor="python",
        inputs=[VarSpec(name="message")],
        locals=[LocalVarSpec(name="code", value="result = message")],
        outputs=[VarSpec(name="result")],
    )

    stop_var = next(v for v in spec.inputs if v.name == STOP_FLAG_VAR)
    assert stop_var.type == "bool"
    assert stop_var.default is False
    assert all(local.name != STOP_FLAG_VAR for local in spec.locals)

    save_agent_spec(tmp_path / "auto_stop.yaml", spec)
    saved = yaml.safe_load((tmp_path / "auto_stop.yaml").read_text()) or {}
    stop_inputs = [v for v in saved.get("inputs", []) if v.get("name") == STOP_FLAG_VAR]
    assert stop_inputs and stop_inputs[0].get("default") is False


def test_repository_persists_stop_flag_with_metadata(tmp_path) -> None:
    spec = AgentSpec(
        name="example",
        title_ua="example",
        description_ua=None,
        kind="atomic",
        executor="python",
        inputs=[VarSpec(name="message")],
        locals=[LocalVarSpec(name="code", value="result = message")],
        outputs=[VarSpec(name="result")],
    )
    repo = AgentRepository(tmp_path)
    repo.save(spec)

    saved = yaml.safe_load((tmp_path / "example.yaml").read_text()) or {}
    stop_inputs = [v for v in saved.get("inputs", []) if v.get("name") == ExecutionEngine.STOP_FLAG_VAR]

    assert stop_inputs
    stop_entry = stop_inputs[0]
    assert stop_entry.get("type") == "bool"
    assert stop_entry.get("default") is False

    fresh_repo = AgentRepository(tmp_path)
    loaded = fresh_repo.get("example")
    stop_var = next(v for v in loaded.inputs if v.name == ExecutionEngine.STOP_FLAG_VAR)
    assert stop_var.default is False
    assert stop_var.type == "bool"


def test_execution_state_status_and_error_persistence(tmp_path) -> None:
    success_spec = AgentSpec(
        name="ok_agent",
        title_ua="ok_agent",
        description_ua=None,
        kind="atomic",
        executor="python",
        inputs=[],
        locals=[LocalVarSpec(name="code", value="result = 'done'")],
        outputs=[VarSpec(name="result")],
    )
    failing_spec = AgentSpec(
        name="fail_agent",
        title_ua="fail_agent",
        description_ua=None,
        kind="atomic",
        executor="shell",
        inputs=[VarSpec(name="command")],
        locals=[],
        outputs=[VarSpec(name="return_code")],
    )
    save_agent_spec(tmp_path / "ok_agent.yaml", success_spec)
    save_agent_spec(tmp_path / "fail_agent.yaml", failing_spec)

    runs_dir = tmp_path / "runs"
    engine = ExecutionEngine(repository=AgentRepository(tmp_path), runs_dir=runs_dir)

    state = engine.run_to_completion("ok_agent", input_json={})
    assert state.status == "ok"
    ok_payload = json.loads((runs_dir / state.run_id / "state.json").read_text())
    assert ok_payload["status"] == "ok"
    assert ok_payload["ok"] is True

    with pytest.raises(RuntimeError):
        engine.run_to_completion("fail_agent", input_json={"command": "false"})

    state_files = sorted(runs_dir.glob("*/state.json"), key=lambda path: path.stat().st_mtime)
    error_payload = json.loads(state_files[-1].read_text())
    assert error_payload["status"] == "error"
    assert error_payload["ok"] is False
    assert error_payload.get("error")


def test_missing_inputs_return_blocked_state(tmp_path) -> None:
    spec = AgentSpec(
        name="needs_input",
        title_ua="needs_input",
        description_ua=None,
        kind="atomic",
        executor="python",
        inputs=[VarSpec(name="text")],
        locals=[LocalVarSpec(name="code", value="output = text")],
        outputs=[VarSpec(name="output")],
    )
    save_agent_spec(tmp_path / "needs_input.yaml", spec)

    engine = ExecutionEngine(repository=AgentRepository(tmp_path), runs_dir=tmp_path / "runs")
    state = engine.run_to_completion("needs_input", input_json={})

    assert state.status == "blocked"
    assert state.ok is False
    assert state.missing_inputs == ["text"]
    assert state.error is None

    persisted = json.loads((tmp_path / "runs" / state.run_id / "state.json").read_text())
    assert persisted["status"] == "blocked"
    assert persisted["missing_inputs"] == ["text"]


def test_composite_lane_barrier_and_skip(tmp_path) -> None:
    _save_atomic(tmp_path, "emit_first", "first_value = 'first'", "first_value")
    _save_atomic(tmp_path, "emit_second", "second_value = 'second'", "second_value")
    _save_atomic(tmp_path, "emit_always", "always_value = 'always'", "always_value")

    workflow = AgentSpec(
        name="workflow",
        title_ua="workflow",
        description_ua=None,
        kind="composite",
        inputs=[VarSpec(name="should_run")],
        locals=[],
        outputs=[],
        graph=GraphSpec(
            lanes=[
                LaneSpec(items=[AgentItemSpec(id="a1", agent="emit_first", bindings=[], ui=None)]),
                LaneSpec(
                    items=[
                        AgentItemSpec(
                            id="skip_me",
                            agent="emit_second",
                            when=WhenSpec(var="should_run", equals=True),
                            bindings=[],
                            ui=None,
                        ),
                        AgentItemSpec(id="always", agent="emit_always", bindings=[], ui=None),
                    ]
                ),
            ]
        ),
    )
    save_agent_spec(tmp_path / "workflow.yaml", workflow)

    engine = ExecutionEngine(repository=AgentRepository(tmp_path), runs_dir=tmp_path / "runs")
    state = engine.run_to_completion("workflow", input_json={"should_run": False})

    assert state.vars["first_value"] == "first"
    assert state.vars["always_value"] == "always"
    assert "second_value" not in state.vars


def test_self_call_stops_on_max_steps(tmp_path) -> None:
    loop_spec = AgentSpec(
        name="loop",
        title_ua="loop",
        description_ua=None,
        kind="composite",
        inputs=[],
        locals=[],
        outputs=[],
        graph=GraphSpec(lanes=[LaneSpec(items=[AgentItemSpec(id="self", agent="loop", bindings=[], ui=None)])]),
    )
    save_agent_spec(tmp_path / "loop.yaml", loop_spec)

    engine = ExecutionEngine(repository=AgentRepository(tmp_path), runs_dir=tmp_path / "runs", max_total_steps=3, max_depth=5)

    with pytest.raises(RuntimeError):
        engine.run_to_completion("loop", input_json={})


def test_bindings_ctx_to_input_and_output_to_ctx(tmp_path) -> None:
    echo_spec = AgentSpec(
        name="echo_python",
        title_ua="echo",
        description_ua=None,
        kind="atomic",
        executor="python",
        inputs=[VarSpec(name="text")],
        locals=[LocalVarSpec(name="code", value="text = str(text)")],
        outputs=[VarSpec(name="text")],
    )
    save_agent_spec(tmp_path / "echo_python.yaml", echo_spec)

    composite = AgentSpec(
        name="wrapper",
        title_ua="wrapper",
        description_ua=None,
        kind="composite",
        inputs=[VarSpec(name="body")],
        locals=[],
        outputs=[],
        graph=GraphSpec(
            lanes=[
                LaneSpec(
                    items=[
                        AgentItemSpec(
                            id="echo1",
                            agent="echo_python",
                            bindings=[
                                BindingSpec(
                                    from_agent_item_id="__CTX__",
                                    from_var="body",
                                    to_agent_item_id="echo1",
                                    to_var="text",
                                )
                            ],
                            ui=None,
                        )
                    ]
                )
            ],
            ctx_bindings=[
                BindingSpec(
                    from_agent_item_id="echo1",
                    from_var="text",
                    to_agent_item_id="__CTX__",
                    to_var="echo_output",
                )
            ],
        ),
    )
    save_agent_spec(tmp_path / "wrapper.yaml", composite)

    engine = ExecutionEngine(repository=AgentRepository(tmp_path), runs_dir=tmp_path / "runs")
    state = engine.run_to_completion("wrapper", input_json={"body": "hello"})

    assert state.vars["text"] == "hello"
    assert state.vars["echo1.text"] == "hello"
    assert state.vars["echo_output"] == "hello"


def test_stop_flag_blocks_following_items(tmp_path) -> None:
    stopper = AgentSpec(
        name="stopper",
        title_ua="stopper",
        description_ua=None,
        kind="atomic",
        executor="python",
        inputs=[],
        locals=[LocalVarSpec(name="code", value=f"{ExecutionEngine.STOP_FLAG_VAR} = True")],
        outputs=[VarSpec(name=ExecutionEngine.STOP_FLAG_VAR)],
    )
    runner = AgentSpec(
        name="runner",
        title_ua="runner",
        description_ua=None,
        kind="atomic",
        executor="python",
        inputs=[],
        locals=[LocalVarSpec(name="code", value="ran = True")],
        outputs=[VarSpec(name="ran")],
    )
    composite = AgentSpec(
        name="stop_flow",
        title_ua="stop_flow",
        description_ua=None,
        kind="composite",
        inputs=[],
        locals=[],
        outputs=[],
        graph=GraphSpec(
            lanes=[
                LaneSpec(
                    items=[
                        AgentItemSpec(
                            id="stop",
                            agent="stopper",
                            bindings=[],
                            ui=UiPlacementSpec(lane_index=0, order=0),
                        ),
                        AgentItemSpec(
                            id="runner",
                            agent="runner",
                            bindings=[],
                            ui=UiPlacementSpec(lane_index=0, order=1),
                        ),
                    ]
                )
            ]
        ),
    )

    repo = AgentRepository(tmp_path)
    save_agent_spec(tmp_path / "stopper.yaml", stopper)
    save_agent_spec(tmp_path / "runner.yaml", runner)
    save_agent_spec(tmp_path / "stop_flow.yaml", composite)

    engine = ExecutionEngine(repository=repo, runs_dir=tmp_path / "runs")
    state = engine.run_to_completion("stop_flow", input_json={})

    assert state.vars[ExecutionEngine.STOP_FLAG_VAR] is True
    assert "ran" not in state.vars
    assert all(entry.get("agent") != "runner" for entry in state.trace)


def test_stop_flag_injected_as_input(tmp_path) -> None:
    basic = AgentSpec(
        name="basic",
        title_ua="basic",
        description_ua=None,
        kind="atomic",
        executor="python",
        inputs=[],
        locals=[LocalVarSpec(name="code", value="pass")],
        outputs=[],
    )
    save_agent_spec(tmp_path / "basic.yaml", basic)

    repo = AgentRepository(tmp_path)
    loaded = repo.get("basic")

    assert any(inp.name == ExecutionEngine.STOP_FLAG_VAR for inp in loaded.inputs)
    assert all(local.name != ExecutionEngine.STOP_FLAG_VAR for local in loaded.locals)

    engine = ExecutionEngine(repository=repo, runs_dir=tmp_path / "runs")
    state = engine.run_to_completion("basic", input_json={})

    assert state.status == "ok"
    assert state.vars[ExecutionEngine.STOP_FLAG_VAR] is False


def test_llm_alias_result_output(tmp_path) -> None:
    llm_agent = AgentSpec(
        name="llm_alias",
        title_ua="llm_alias",
        description_ua=None,
        kind="atomic",
        executor="llm",
        inputs=[VarSpec(name="prompt")],
        locals=[],
        outputs=[VarSpec(name="результат")],
    )
    save_agent_spec(tmp_path / "llm_alias.yaml", llm_agent)

    engine = ExecutionEngine(repository=AgentRepository(tmp_path), runs_dir=tmp_path / "runs")
    state = engine.run_to_completion("llm_alias", input_json={"prompt": "hello"})

    assert state.vars["результат"].startswith("LLM: hello")


class RecordingLLMClient(LLMClient):
    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url
        self.model = model
        self.calls: list[dict[str, object]] = []

    def generate(self, prompt: str, **kwargs: object) -> str:  # noqa: ANN003
        self.calls.append({"prompt": prompt, "kwargs": kwargs})
        return f"{self.model}@{self.base_url}:{kwargs.get('temperature')}"


def test_llm_variables_required(tmp_path) -> None:
    llm_spec = AgentSpec(
        name="llm_configured",
        title_ua="llm_configured",
        description_ua=None,
        kind="atomic",
        executor="llm",
        inputs=[VarSpec(name="prompt"), VarSpec(name="host"), VarSpec(name="model"), VarSpec(name="temperature")],
        locals=[LocalVarSpec(name="parse_json", value=False)],
        outputs=[VarSpec(name="output_text")],
    )
    save_agent_spec(tmp_path / "llm_configured.yaml", llm_spec)

    created: dict[str, RecordingLLMClient] = {}

    def factory(host: str, model: str) -> RecordingLLMClient:
        client = RecordingLLMClient(host, model)
        created["client"] = client
        return client

    engine = ExecutionEngine(repository=AgentRepository(tmp_path), runs_dir=tmp_path / "runs", llm_client_factory=factory)
    state = engine.run_to_completion(
        "llm_configured",
        input_json={"prompt": "ping", "host": "http://llm.local", "model": "demo-model", "temperature": 0.5},
    )

    assert created["client"].base_url == "http://llm.local"
    assert created["client"].model == "demo-model"
    assert created["client"].calls and created["client"].calls[0]["kwargs"].get("temperature") == 0.5
    assert state.vars["output_text"].startswith("demo-model@http://llm.local")

    blocked = engine.run_to_completion("llm_configured", input_json={"prompt": "missing host", "model": "demo-model"})

    assert blocked.status == "blocked"
    assert set(blocked.missing_inputs or []) == {"host", "temperature"}


def test_python_exec_from_input(tmp_path) -> None:
    spec = AgentSpec(
        name="python_eval_input",
        title_ua="python_eval_input",
        description_ua=None,
        kind="atomic",
        executor="python",
        inputs=[VarSpec(name="code"), VarSpec(name="input")],
        locals=[],
        outputs=[VarSpec(name="output")],
    )
    save_agent_spec(tmp_path / "python_eval_input.yaml", spec)

    engine = ExecutionEngine(repository=AgentRepository(tmp_path), runs_dir=tmp_path / "runs")
    state = engine.run_to_completion(
        "python_eval_input",
        input_json={"code": "output = input.get('x', 0) * 2", "input": {"x": 3}},
    )

    assert state.vars["output"] == 6


def test_json_pack_and_extract(tmp_path) -> None:
    pack = AgentSpec(
        name="json_pack",
        title_ua="json_pack",
        description_ua=None,
        kind="atomic",
        executor="python",
        inputs=[VarSpec(name="ключ"), VarSpec(name="значення")],
        locals=[
            LocalVarSpec(
                name="code",
                value="import json as json_lib\npayload = {ключ: значення}\noutput = json_lib.dumps(payload, ensure_ascii=False)",
            )
        ],
        outputs=[VarSpec(name="output")],
    )
    extract = AgentSpec(
        name="json_extract",
        title_ua="json_extract",
        description_ua=None,
        kind="atomic",
        executor="python",
        inputs=[VarSpec(name="json"), VarSpec(name="ключ")],
        locals=[
            LocalVarSpec(
                name="code",
                value="import json as json_lib\nsource = json\nif isinstance(source, str):\n    source = json_lib.loads(source)\noutput = source.get(ключ) if isinstance(source, dict) else None",
            )
        ],
        outputs=[VarSpec(name="output")],
    )
    save_agent_spec(tmp_path / "json_pack.yaml", pack)
    save_agent_spec(tmp_path / "json_extract.yaml", extract)

    repo = AgentRepository(tmp_path)
    engine = ExecutionEngine(repository=repo, runs_dir=tmp_path / "runs")
    packed = engine.run_to_completion("json_pack", input_json={"ключ": "answer", "значення": 42})
    extracted = engine.run_to_completion(
        "json_extract", input_json={"json": packed.vars["output"], "ключ": "answer"}
    )

    assert packed.vars["output"] == "{\"answer\": 42}"
    assert extracted.vars["output"] == 42


@pytest.mark.parametrize(
    "task_text,expected_plan",
    [
        ("коротке завдання", False),
        ("це дуже довгий текст задачі який точно перевищує ліміт символів", True),
    ],
)
def test_workflow_demo_branching(task_text, expected_plan, tmp_path) -> None:
    repo = AgentRepository(Path("agents"))
    engine = ExecutionEngine(repository=repo, runs_dir=tmp_path / "runs")

    state = engine.run_to_completion("workflow_demo", input_json={"task_text": task_text})

    assert state.vars["обрати_план"] is expected_plan
    assert state.vars["класифікація"] is expected_plan
    assert state.vars["вихідний_запит"] == task_text
    if expected_plan:
        assert state.vars["гілка_так"] == task_text
        assert "План" in state.vars["відповідь"]
    else:
        assert state.vars["гілка_ні"] == task_text
        assert "Проста" in state.vars["відповідь"]
