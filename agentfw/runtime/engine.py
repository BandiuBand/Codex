from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from agentfw.core.agent_spec import AgentItemSpec, AgentSpec, BindingSpec, GraphSpec, LaneSpec, WhenSpec
from agentfw.io.agent_yaml import load_agent_spec, save_agent_spec
from agentfw.llm.base import DummyLLMClient, LLMClient, OllamaLLMClient
from agentfw.llm.json_extract import extract_first_json
from agentfw.runtime.chat_agent import ChatAgentGateway


def _find_agents_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "agents"


class AgentRepository:
    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = base_dir or _find_agents_dir()
        self._cache: Dict[str, AgentSpec] = {}

    def list(self) -> List[AgentSpec]:
        agents: List[AgentSpec] = []
        if not self.base_dir.exists():
            return agents
        for pattern in ("*.yaml", "*.yml"):
            for path in sorted(self.base_dir.glob(pattern)):
                try:
                    agents.append(self.get(path.stem))
                except Exception:
                    continue
        return agents

    def get(self, name: str) -> AgentSpec:
        if name in self._cache:
            return self._cache[name]
        for suffix in (".yaml", ".yml"):
            path = self.base_dir / f"{name}{suffix}"
            if path.exists():
                spec = load_agent_spec(path)
                self._cache[name] = spec
                return spec
        raise KeyError(f"Agent '{name}' not found")

    def save(self, spec: AgentSpec) -> None:
        path = self.base_dir / f"{spec.name}.yaml"
        save_agent_spec(path, spec)
        self._cache[spec.name] = spec


@dataclass
class ExecutionTrace:
    entries: List[Dict[str, Any]] = field(default_factory=list)

    def add(self, payload: Dict[str, Any]) -> None:
        self.entries.append(payload)


@dataclass
class ExecutionState:
    agent_name: str
    run_id: str
    status: str
    vars: Dict[str, Any]
    trace: List[Dict[str, Any]]
    ok: bool
    error: Optional[str] = None
    missing_inputs: Optional[List[str]] = None
    questions_to_user: Optional[List[str]] = None
    why_blocked: Optional[str] = None


class BlockedExecution(Exception):
    def __init__(
        self,
        *,
        missing_inputs: Optional[List[str]] = None,
        questions_to_user: Optional[List[str]] = None,
        why_blocked: Optional[str] = None,
    ) -> None:
        super().__init__(why_blocked or "execution blocked")
        self.missing_inputs = missing_inputs
        self.questions_to_user = questions_to_user
        self.why_blocked = why_blocked


class ExecutionContext:
    def __init__(self, variables: Optional[Dict[str, Any]] = None) -> None:
        self.variables: Dict[str, Any] = variables or {}

    def get(self, key: str, default: Any = None) -> Any:
        return self.variables.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.variables[key] = value


class AtomicExecutor:
    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        llm_client_factory: Optional[Callable[[str, str], LLMClient]] = None,
    ) -> None:
        self.llm_client = llm_client or DummyLLMClient()
        self.llm_client_factory = llm_client_factory

    def run(self, spec: AgentSpec, ctx: ExecutionContext) -> Dict[str, Any]:
        if spec.executor == "llm":
            return self._run_llm(spec, ctx)
        if spec.executor == "python":
            return self._run_python(spec, ctx)
        if spec.executor == "shell":
            return self._run_shell(spec, ctx)
        raise ValueError(f"Unsupported executor '{spec.executor}'")

    def _run_llm(self, spec: AgentSpec, ctx: ExecutionContext) -> Dict[str, Any]:
        prompt_template = str(ctx.get("prompt", ""))
        prompt = prompt_template.format(**ctx.variables)
        options = self._build_llm_options(ctx)
        host, model = self._gather_llm_config(spec, ctx, options)
        if model:
            options["model"] = model
        client = self._resolve_llm_client(host, options.get("model"))
        output_text = client.generate(prompt, **options)
        parse_json = bool(ctx.get("parse_json", False))
        result: Dict[str, Any] = {"output_text": output_text}
        output_names = {v.name for v in spec.outputs}
        if "результат" in output_names:
            result["результат"] = output_text
        if parse_json:
            parsed, reason = extract_first_json(output_text)
            result["output_json"] = parsed
            if isinstance(parsed, dict):
                if parsed.get("status") == "blocked":
                    raise BlockedExecution(
                        missing_inputs=parsed.get("missing_inputs"),
                        questions_to_user=parsed.get("questions_to_user"),
                        why_blocked=parsed.get("why_blocked") or parsed.get("reason"),
                    )
                preferred_answer = parsed.get("answer") or parsed.get("result") or parsed.get("output")
                if preferred_answer is not None and "результат" in output_names:
                    result["результат"] = preferred_answer
            if reason:
                result["json_error"] = reason
        return self._filter_outputs(result, spec)

    def _build_llm_options(self, ctx: ExecutionContext) -> Dict[str, Any]:
        options_raw = ctx.get("options", {})
        options: Dict[str, Any] = {}
        if isinstance(options_raw, dict):
            options.update(options_raw)
        elif isinstance(options_raw, str):
            try:
                parsed = json.loads(options_raw)
                if isinstance(parsed, dict):
                    options.update(parsed)
            except json.JSONDecodeError:
                options = {}
        temp = ctx.get("temperature")
        if temp is not None:
            try:
                options["temperature"] = float(temp)
            except (TypeError, ValueError):
                options["temperature"] = temp
        return options

    def _gather_llm_config(self, spec: AgentSpec, ctx: ExecutionContext, options: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
        declared_names = {v.name for v in spec.inputs} | {v.name for v in spec.locals}
        host_keys = ("ollama_host", "llm_host", "host")
        model_keys = ("ollama_model", "llm_model", "model")
        host = self._first_present(ctx, host_keys)
        model = self._first_present(ctx, model_keys)
        if model is None:
            model = options.get("model") if isinstance(options.get("model"), (str, bool, int, float)) else None
        requires_host = any(key in declared_names for key in host_keys)
        requires_model = any(key in declared_names for key in model_keys)
        if requires_host and host is None:
            raise ValueError("LLM agent requires host via змінні агента")
        if requires_model and model is None:
            raise ValueError("LLM agent requires model via змінні агента")
        return str(host) if host is not None else None, str(model) if model is not None else None

    def _resolve_llm_client(self, host: Optional[str], model: Optional[str]) -> LLMClient:
        if host:
            factory = self.llm_client_factory or (lambda base_url, chosen_model: OllamaLLMClient(base_url=base_url, model=chosen_model or ""))
            return factory(host, model or "")
        return self.llm_client

    @staticmethod
    def _first_present(ctx: ExecutionContext, keys: tuple[str, ...]) -> Optional[Any]:
        for key in keys:
            value = ctx.get(key)
            if value is not None:
                return value
        return None

    def _run_python(self, spec: AgentSpec, ctx: ExecutionContext) -> Dict[str, Any]:
        code = str(ctx.get("code", ""))
        sandbox: Dict[str, Any] = {}
        sandbox.update(ctx.variables)
        stdout_lines: List[str] = []

        def capture_print(*args: Any, **kwargs: Any) -> None:  # noqa: ARG001
            stdout_lines.append(" ".join(map(str, args)))

        sandbox["print"] = capture_print
        try:
            compiled = compile(code, "<agent_python>", "exec")
            exec(compiled, sandbox, sandbox)  # noqa: S102
        except BlockedExecution:
            raise
        except Exception as exc:  # noqa: BLE001
            sandbox["error"] = str(exc)
        if stdout_lines:
            sandbox["stdout"] = "\n".join(stdout_lines)
        return self._filter_outputs(sandbox, spec)

    def _run_shell(self, spec: AgentSpec, ctx: ExecutionContext) -> Dict[str, Any]:
        import subprocess

        command = ctx.get("command")
        if command is None:
            raise ValueError("Shell executor requires 'command'")
        cwd = ctx.get("cwd")
        timeout = ctx.get("timeout")
        allow_failure = bool(ctx.get("allow_failure", False))
        if ctx.get("env"):
            raise ValueError("env override is not allowed")
        if isinstance(command, list):
            cmd = [str(x) for x in command]
        else:
            cmd = str(command).split()
        try:
            completed = subprocess.run(  # noqa: S603, PLW1510
                cmd,
                cwd=str(cwd) if cwd else None,
                timeout=float(timeout) if timeout is not None else None,
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception as exc:  # noqa: BLE001
            return self._filter_outputs({"return_code": -1, "stdout": "", "stderr": str(exc), "ok": False}, spec)
        result = {
            "return_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "ok": completed.returncode == 0,
        }
        if completed.returncode != 0 and not allow_failure:
            raise RuntimeError(f"Shell command failed with code {completed.returncode}")
        return self._filter_outputs(result, spec)

    @staticmethod
    def _filter_outputs(values: Dict[str, Any], spec: AgentSpec) -> Dict[str, Any]:
        allowed = {v.name for v in spec.outputs}
        return {key: val for key, val in values.items() if key in allowed}


class ExecutionEngine:
    def __init__(
        self,
        repository: Optional[AgentRepository] = None,
        llm_client: Optional[LLMClient] = None,
        llm_client_factory: Optional[Callable[[str, str], LLMClient]] = None,
        runs_dir: Optional[Path] = None,
        max_total_steps: int = 10_000,
        max_depth: int = 50,
        chat_gateway: Optional[ChatAgentGateway] = None,
    ) -> None:
        self.repository = repository or AgentRepository()
        llm_mode = (os.getenv("AGENTFW_DEFAULT_LLM") or "dummy").lower()
        fallback_llm: LLMClient
        if llm_mode == "ollama":
            fallback_llm = OllamaLLMClient()
        else:
            fallback_llm = DummyLLMClient()

        default_llm = llm_client or fallback_llm
        self.atomic = AtomicExecutor(llm_client=default_llm, llm_client_factory=llm_client_factory)
        self.runs_dir = runs_dir or Path("runs")
        self.max_total_steps = max_total_steps
        self.max_depth = max_depth
        self._step_counter = 0
        self.chat_gateway = chat_gateway or ChatAgentGateway()

    def run_to_completion(
        self,
        agent_name: str,
        input_json: Dict[str, Any],
        *,
        raise_on_error: bool = True,
    ) -> ExecutionState:
        self._step_counter = 0
        spec = self.repository.get(agent_name)
        normalized_input = dict(input_json or {})
        if agent_name == "adaptive_task_agent":
            user_msg = str(
                normalized_input.get("user_message")
                or normalized_input.get("завдання")
                or normalized_input.get("task")
                or ""
            ).strip()
            normalized_input.setdefault("завдання", user_msg)
            normalized_input["user_message"] = user_msg
        if "user_message" not in normalized_input and "завдання" in normalized_input:
            normalized_input["user_message"] = normalized_input.get("завдання")
        ctx_vars: Dict[str, Any] = dict(normalized_input)
        ctx_vars.setdefault("chat_gateway", self.chat_gateway)
        for local in spec.locals:
            ctx_vars.setdefault(local.name, local.value)
        ctx = ExecutionContext(ctx_vars)
        trace = ExecutionTrace()
        try:
            self._execute_agent(spec, ctx, trace, depth=0)
            vars_clean = self._clean_vars(ctx.variables)
            state = ExecutionState(
                agent_name=agent_name,
                run_id=str(uuid.uuid4()),
                status="ok",
                ok=True,
                vars=vars_clean,
                trace=trace.entries,
                error=None,
            )
        except BlockedExecution as blocked:
            vars_clean = self._clean_vars(ctx.variables)
            state = ExecutionState(
                agent_name=agent_name,
                run_id=str(uuid.uuid4()),
                status="blocked",
                ok=False,
                vars=vars_clean,
                trace=trace.entries,
                error=None,
                missing_inputs=blocked.missing_inputs,
                questions_to_user=blocked.questions_to_user,
                why_blocked=blocked.why_blocked or str(blocked),
            )
        except Exception as exc:  # noqa: BLE001
            vars_clean = self._clean_vars(ctx.variables)
            state = ExecutionState(
                agent_name=agent_name,
                run_id=str(uuid.uuid4()),
                status="error",
                ok=False,
                vars=vars_clean,
                trace=trace.entries,
                error=str(exc),
            )
        self._persist_state(state)
        if raise_on_error and (not state.ok and state.status != "blocked"):
            raise RuntimeError(state.error or "execution failed")
        return state

    def _execute_agent(
        self,
        spec: AgentSpec,
        ctx: ExecutionContext,
        trace: ExecutionTrace,
        depth: int,
    ) -> None:
        self._require_inputs(spec, ctx, depth=depth)
        if self._step_counter >= self.max_total_steps:
            raise RuntimeError("max_total_steps exceeded")
        if depth > self.max_depth:
            raise RuntimeError("max_depth exceeded")
        self._step_counter += 1
        if spec.kind == "atomic":
            outputs = self.atomic.run(spec, ctx)
            ctx.variables.update(outputs)
            trace.add({"agent": spec.name, "kind": "atomic", "outputs": dict(outputs)})
            return
        if spec.graph is None:
            raise ValueError("Composite agent requires graph")
        self._execute_graph(spec.graph, ctx, trace, depth)
        trace.add({"agent": spec.name, "kind": "composite_end"})

    def _execute_graph(self, graph: GraphSpec, ctx: ExecutionContext, trace: ExecutionTrace, depth: int) -> None:
        all_bindings: List[BindingSpec] = []
        for lane in graph.lanes:
            for item in lane.items:
                all_bindings.extend(item.bindings)
        ctx_bindings: List[BindingSpec] = list(getattr(graph, "ctx_bindings", []))
        for lane_index, lane in enumerate(graph.lanes):
            items = sorted(lane.items, key=lambda i: i.ui.order if i.ui else 0)
            for item in items:
                spec = self.repository.get(item.agent)
                if not self._should_run(item.when, ctx):
                    trace.add({"item_id": item.id, "agent": item.agent, "skipped": True, "lane": lane_index})
                    continue
                child_ctx = self._build_child_context(spec, ctx, item, all_bindings)
                self._execute_agent(spec, child_ctx, trace, depth + 1)
                for name, value in child_ctx.variables.items():
                    if name == "chat_gateway":
                        continue
                    ctx.set(f"{item.id}.{name}", value)
                    ctx.set(name, value)
                for binding in ctx_bindings:
                    if binding.from_agent_item_id != item.id or binding.to_agent_item_id != "__CTX__":
                        continue
                    ctx.set(binding.to_var, child_ctx.get(binding.from_var))
                filtered_child = {k: v for k, v in child_ctx.variables.items() if k != "chat_gateway"}
                trace.add(
                    {
                        "item_id": item.id,
                        "agent": item.agent,
                        "lane": lane_index,
                        "outputs": filtered_child,
                    }
                )

    @staticmethod
    def _clean_vars(values: Dict[str, Any]) -> Dict[str, Any]:
        return {key: value for key, value in values.items() if key != "chat_gateway"}

    def _build_child_context(
        self,
        spec: AgentSpec,
        parent_ctx: ExecutionContext,
        target_item: AgentItemSpec,
        bindings: List[BindingSpec],
    ) -> ExecutionContext:
        child_vars: Dict[str, Any] = {}
        if "chat_gateway" in parent_ctx.variables:
            child_vars["chat_gateway"] = parent_ctx.get("chat_gateway")
        for local in spec.locals:
            child_vars.setdefault(local.name, local.value)
        for binding in bindings:
            if binding.to_agent_item_id != target_item.id:
                continue
            if binding.from_agent_item_id == "__CTX__":
                value = parent_ctx.get(binding.from_var)
            else:
                prefixed = f"{binding.from_agent_item_id}.{binding.from_var}"
                value = parent_ctx.get(prefixed, parent_ctx.get(binding.from_var))
            child_vars[binding.to_var] = value
        return ExecutionContext(child_vars)

    def _require_inputs(self, spec: AgentSpec, ctx: ExecutionContext, *, depth: int) -> None:
        if depth > 0:
            return
        missing = [var.name for var in spec.inputs if ctx.get(var.name) is None]
        if missing:
            raise BlockedExecution(
                missing_inputs=missing,
                questions_to_user=[],
                why_blocked="Не вистачає вхідних змінних",
            )

    @staticmethod
    def _should_run(when: Optional[WhenSpec], ctx: ExecutionContext) -> bool:
        if when is None:
            return True
        return ctx.get(when.var) == when.equals

    def _persist_state(self, state: ExecutionState) -> None:
        run_dir = self.runs_dir / state.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        state_payload = {
            "agent": state.agent_name,
            "run_id": state.run_id,
            "status": state.status,
            "ok": state.ok,
            "vars": state.vars,
            "error": state.error,
            "missing_inputs": state.missing_inputs,
            "questions_to_user": state.questions_to_user,
            "why_blocked": state.why_blocked,
            "created_at": int(time.time()),
        }
        trace_payload = {"trace": state.trace}
        (run_dir / "state.json").write_text(json.dumps(state_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_dir / "trace.json").write_text(json.dumps(trace_payload, ensure_ascii=False, indent=2), encoding="utf-8")


__all__ = [
    "AgentRepository",
    "BlockedExecution",
    "ExecutionContext",
    "ExecutionEngine",
    "ExecutionState",
    "ExecutionTrace",
]
