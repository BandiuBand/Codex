from __future__ import annotations

from agentfw.core.agent import Agent, ChildRef, Lane, Link, VarDecl
from agentfw.io.agent_yaml import save_agent
from agentfw.runtime.builtins import BuiltinAgentRegistry
from agentfw.runtime.engine import AgentRepository, ExecutionEngine


def test_run_if_skips_child_without_blocking_lane(tmp_path) -> None:
    registry = BuiltinAgentRegistry()
    registry.register("std.skipme", lambda ctx: {"$out.called": True})
    registry.register("std.ok", lambda ctx: {"$out.value": "done"})

    parent = Agent(
        id="parent",
        name="parent",
        description=None,
        inputs=[],
        locals=[VarDecl(name="allow", type="bool")],
        outputs=[VarDecl(name="value", type="string")],
        children={
            "a": ChildRef(id="a", ref="std.skipme", run_if="$local.allow == true"),
            "b": ChildRef(id="b", ref="std.ok"),
        },
        lanes=[Lane(id="L1", agents=["a", "b"])],
        links=[],
    )

    parent.links.append(Link(src="b.$out.value", dst="$out.value"))

    save_agent(tmp_path / "parent.yaml", parent)

    engine = ExecutionEngine(repository=AgentRepository(tmp_path), builtin_registry=registry)

    state = engine.run_to_completion("parent", input_json={}, locals_json={"allow": False})

    assert state.out.get("value") == "done"
