from __future__ import annotations

from agentfw.core.agent import Agent, ChildRef, Lane, Link, VarDecl
from agentfw.io.agent_yaml import save_agent
from agentfw.runtime.builtins import BuiltinAgentRegistry
from agentfw.runtime.engine import AgentRepository, ExecutionEngine


def test_local_to_child_input_link(tmp_path) -> None:
    registry = BuiltinAgentRegistry()
    registry.register("std.echo", lambda ctx: {"$out.echo": ctx.get("$in.value")})

    child_agent = Agent(
        id="std.echo",
        name="std.echo",
        description=None,
        inputs=[VarDecl(name="value", type="string")],
        locals=[],
        outputs=[VarDecl(name="echo", type="string")],
        children={},
        lanes=[],
        links=[],
    )
    save_agent(tmp_path / "std.echo.yaml", child_agent)

    parent = Agent(
        id="parent",
        name="parent",
        description=None,
        inputs=[],
        locals=[VarDecl(name="x", type="string")],
        outputs=[VarDecl(name="result", type="string")],
        children={"c1": ChildRef(id="c1", ref="std.echo")},
        lanes=[Lane(id="1", agents=["c1"])],
        links=[
            Link(src="$local.x", dst="c1.$in.value"),
            Link(src="c1.$out.echo", dst="$out.result"),
        ],
    )
    save_agent(tmp_path / "parent.yaml", parent)

    engine = ExecutionEngine(repository=AgentRepository(tmp_path), builtin_registry=registry)
    state = engine.run_to_completion("parent", input_json={}, locals_json={"x": "hello"})

    assert state.out["result"] == "hello"
