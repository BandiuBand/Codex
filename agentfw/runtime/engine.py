from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from agentfw.core.agent import Agent, ChildRef, Lane
from agentfw.io.agent_yaml import load_agent
from agentfw.runtime.builtins import BUILTIN_PORTS, BuiltinAgentRegistry, build_default_registry
from agentfw.runtime.expr import eval_expr


def _find_agents_dir() -> Path:
    env_dir = Path(__file__).resolve().parents[2] / "agents"
    return env_dir


class AgentRepository:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or _find_agents_dir()
        self._cache: Dict[str, Agent] = {}

    def list(self) -> List[Agent]:
        agents: List[Agent] = []
        for pattern in ("*.yaml", "*.yml"):
            for path in sorted(self.base_dir.glob(pattern)):
                try:
                    agents.append(self.get(path.stem))
                except Exception:
                    continue
        return agents

    def get(self, agent_id: str) -> Agent:
        if agent_id in self._cache:
            return self._cache[agent_id]

        for name in (f"{agent_id}.yaml", f"{agent_id}.yml"):
            path = self.base_dir / name
            if path.exists():
                agent = load_agent(path)
                self._cache[agent_id] = agent
                return agent

        raise KeyError(f"Agent '{agent_id}' not found")


@dataclass
class ExecutionTrace:
    entries: List[Dict[str, Any]] = field(default_factory=list)

    def add(self, **payload: Any) -> None:
        self.entries.append(payload)


@dataclass
class ExecutionState:
    agent_id: str
    run_id: str
    finished: bool
    failed: bool
    out: Dict[str, Any]
    locals: Dict[str, Any]
    trace: ExecutionTrace


class ExecutionContext:
    def __init__(self, variables: Dict[str, Any]) -> None:
        self.variables = variables

    def get(self, name: str, default: Any = None) -> Any:
        return self.variables.get(name, default)

    def set(self, name: str, value: Any) -> None:
        self.variables[name] = value

    def export_with_prefix(self, prefix: str) -> Dict[str, Any]:
        return {f"{prefix}.{k}": v for k, v in self.variables.items()}


class ExecutionEngine:
    def __init__(
        self,
        repository: AgentRepository | None = None,
        builtin_registry: BuiltinAgentRegistry | None = None,
    ) -> None:
        self.repository = repository or AgentRepository()
        self.builtin_registry = builtin_registry or build_default_registry()

    def run_to_completion(
        self, agent_id: str, input_json: Dict[str, Any], locals_json: Optional[Dict[str, Any]] = None
    ) -> ExecutionState:
        run_id = str(int(time.time() * 1000))
        agent = self._get_agent(agent_id)
        context_vars: Dict[str, Any] = {}
        for name, value in (input_json or {}).items():
            context_vars[f"$in.{name}"] = value
        for name, value in (locals_json or {}).items():
            context_vars[f"$local.{name}"] = value

        trace = ExecutionTrace()

        if agent.is_atomic():
            self._execute_atomic(agent, context_vars, trace)
        else:
            self._execute_composite(agent, context_vars, trace)

        out_vars = {k[len("$out."):]: v for k, v in context_vars.items() if k.startswith("$out.")}
        local_vars = {k[len("$local."):]: v for k, v in context_vars.items() if k.startswith("$local.")}

        return ExecutionState(
            agent_id=agent_id,
            run_id=run_id,
            finished=True,
            failed=False,
            out=out_vars,
            locals=local_vars,
            trace=trace,
        )

    def _execute_atomic(self, agent: Agent, context_vars: Dict[str, Any], trace: ExecutionTrace) -> None:
        if not self.builtin_registry.has(agent.id):
            raise ValueError(f"No built-in implementation for atomic agent '{agent.id}'")
        ctx = ExecutionContext(variables={**context_vars})
        result = self.builtin_registry.run(agent.id, ctx)
        for key, value in result.items():
            context_vars[key] = value
        trace.add(agent=agent.id, kind="atomic", vars=dict(result))

    def _execute_composite(self, agent: Agent, context_vars: Dict[str, Any], trace: ExecutionTrace) -> None:
        self._apply_links(agent, context_vars)
        for lane in agent.lanes:
            for child_id in lane.agents:
                child = agent.children.get(child_id)
                if not child:
                    continue
                if not self._should_run_child(child, context_vars):
                    trace.add(agent=agent.id, child=child.id, skipped=True)
                    continue
                child_context = self._build_child_context(child, context_vars)
                self._run_child(child, child_context, context_vars, trace)
                self._apply_links(agent, context_vars)

    def _should_run_child(self, child: ChildRef, context_vars: Dict[str, Any]) -> bool:
        if not child.run_if:
            return True

        def resolver(address: str) -> Any:
            return context_vars.get(address)

        return eval_expr(child.run_if, resolver)

    def _build_child_context(self, child: ChildRef, context_vars: Dict[str, Any]) -> ExecutionContext:
        prefix = f"{child.id}."
        child_vars: Dict[str, Any] = {}
        for key, value in context_vars.items():
            if key.startswith(prefix):
                stripped = key[len(prefix) :]
                child_vars[stripped] = value
        return ExecutionContext(child_vars)

    def _run_child(
        self,
        child: ChildRef,
        child_ctx: ExecutionContext,
        parent_vars: Dict[str, Any],
        trace: ExecutionTrace,
    ) -> None:
        agent = self._get_agent(child.ref)
        if agent.is_atomic():
            if not self.builtin_registry.has(agent.id):
                raise ValueError(f"Unknown builtin agent '{agent.id}' for child '{child.id}'")
            result = self.builtin_registry.run(agent.id, child_ctx)
            for key, value in result.items():
                child_ctx.set(key, value)
            trace.add(agent=child.ref, child=child.id, kind="atomic", vars=dict(result))
        else:
            child_engine = ExecutionEngine(repository=self.repository, builtin_registry=self.builtin_registry)
            child_input = {k[len("$in."):]: v for k, v in child_ctx.variables.items() if k.startswith("$in.")}
            child_locals = {k[len("$local."):]: v for k, v in child_ctx.variables.items() if k.startswith("$local.")}
            nested_state = child_engine.run_to_completion(child.ref, child_input, child_locals)
            for name, value in nested_state.out.items():
                child_ctx.set(f"$out.{name}", value)
            for name, value in nested_state.locals.items():
                child_ctx.set(f"$local.{name}", value)
            trace.add(agent=child.ref, child=child.id, kind="composite", trace=nested_state.trace.entries)

        parent_vars.update(child_ctx.export_with_prefix(child.id))

    def _apply_links(self, agent: Agent, context_vars: Dict[str, Any]) -> None:
        updates: Dict[str, Any] = {}

        def resolve(address: str) -> Any:
            return context_vars[address] if address in context_vars else None

        for link in agent.links:
            value = resolve(link.src)
            updates[link.dst] = value

        context_vars.update(updates)

    def _get_agent(self, agent_id: str) -> Agent:
        try:
            return self.repository.get(agent_id)
        except KeyError:
            if self.builtin_registry.has(agent_id):
                ports = BUILTIN_PORTS.get(agent_id, {})
                return Agent(
                    id=agent_id,
                    name=agent_id,
                    description=None,
                    inputs=ports.get("inputs", []),
                    locals=[],
                    outputs=ports.get("outputs", []),
                    children={},
                    lanes=[],
                    links=[],
                )
            raise


__all__ = ["ExecutionEngine", "ExecutionState", "AgentRepository"]
