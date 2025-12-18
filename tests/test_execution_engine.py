from __future__ import annotations

from pathlib import Path

import pytest

from agentfw.core.agent_spec import AgentItemSpec, AgentSpec, BindingSpec, GraphSpec, LaneSpec, LocalVarSpec, VarSpec, WhenSpec
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

    with pytest.raises(RuntimeError, match="host"):
        engine.run_to_completion("llm_configured", input_json={"prompt": "missing host", "model": "demo-model"})


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
