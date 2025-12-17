from __future__ import annotations

import pytest

from agentfw.core.agent_spec import AgentItemSpec, AgentSpec, BindingSpec, GraphSpec, LaneSpec, LocalVarSpec, VarSpec, WhenSpec
from agentfw.io.agent_yaml import save_agent_spec
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
            ]
        ),
    )
    save_agent_spec(tmp_path / "wrapper.yaml", composite)

    engine = ExecutionEngine(repository=AgentRepository(tmp_path), runs_dir=tmp_path / "runs")
    state = engine.run_to_completion("wrapper", input_json={"body": "hello"})

    assert state.vars["text"] == "hello"
    assert state.vars["echo1.text"] == "hello"
