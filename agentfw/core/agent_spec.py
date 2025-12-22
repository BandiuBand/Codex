from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Union


JsonScalar = Union[str, bool, int, float, None]
JsonValue = Union[JsonScalar, Dict[str, Any], List[Any]]

STOP_FLAG_VAR = "stop_agent_execution"


@dataclass
class VarSpec:
    name: str
    type: Optional[str] = None
    default: Optional[JsonValue] = None


@dataclass
class LocalVarSpec:
    name: str
    value: JsonValue


@dataclass
class WhenSpec:
    var: str
    equals: JsonScalar


@dataclass
class BindingSpec:
    from_agent_item_id: str
    from_var: str
    to_agent_item_id: str
    to_var: str


@dataclass
class UiPlacementSpec:
    lane_index: int
    order: int
    x: Optional[int] = None
    y: Optional[int] = None


@dataclass
class AgentItemSpec:
    id: str
    agent: str
    when: Optional[WhenSpec] = None
    bindings: List[BindingSpec] = field(default_factory=list)
    ui: Optional[UiPlacementSpec] = None


@dataclass
class LaneSpec:
    items: List[AgentItemSpec] = field(default_factory=list)


@dataclass
class GraphSpec:
    lanes: List[LaneSpec] = field(default_factory=list)
    ctx_bindings: List[BindingSpec] = field(default_factory=list)


@dataclass
class AgentSpec:
    name: str
    title_ua: str
    description_ua: Optional[str]
    kind: Literal["atomic", "composite"]
    executor: Optional[Literal["llm", "python", "shell"]] = None
    inputs: List[VarSpec] = field(default_factory=list)
    locals: List[LocalVarSpec] = field(default_factory=list)
    outputs: List[VarSpec] = field(default_factory=list)
    graph: Optional[GraphSpec] = None

    def __post_init__(self) -> None:
        ensure_stop_flag(self.inputs, self.locals)

    def display_title(self) -> str:
        return self.title_ua or self.name


def _parse_var_spec(raw: Any) -> VarSpec:
    if not isinstance(raw, dict):
        raise ValueError("VarSpec must be an object")
    name = str(raw.get("name", "")).strip()
    if not name:
        raise ValueError("VarSpec missing required field 'name'")
    var_type = raw.get("type")
    if var_type is not None:
        var_type = str(var_type)
    default_raw = raw.get("default")
    default: Optional[JsonValue]
    if isinstance(default_raw, (str, bool, int, float, dict, list)) or default_raw is None:
        default = default_raw
    else:
        default = str(default_raw)
    return VarSpec(name=name, type=var_type, default=default)


def ensure_stop_flag(inputs: List[VarSpec], locals_vars: List[LocalVarSpec]) -> None:
    locals_vars[:] = [local for local in locals_vars if local.name != STOP_FLAG_VAR]

    for var in inputs:
        if var.name == STOP_FLAG_VAR:
            if var.type is None:
                var.type = "bool"
            if var.default is None:
                var.default = False
            return

    inputs.append(VarSpec(name=STOP_FLAG_VAR, type="bool", default=False))


def _parse_local_var_spec(raw: Any) -> LocalVarSpec:
    if not isinstance(raw, dict):
        raise ValueError("LocalVarSpec must be an object")
    name = str(raw.get("name", "")).strip()
    if not name:
        raise ValueError("LocalVarSpec missing required field 'name'")
    value_raw = raw.get("value", "")
    value: JsonValue
    if isinstance(value_raw, (str, bool, int, float, dict, list)) or value_raw is None:
        value = value_raw
    else:
        value = str(value_raw)
    return LocalVarSpec(name=name, value=value)


def _parse_when_spec(raw: Any) -> WhenSpec:
    if not isinstance(raw, dict):
        raise ValueError("WhenSpec must be an object")
    var = str(raw.get("var", "")).strip()
    if not var:
        raise ValueError("WhenSpec missing required field 'var'")
    return WhenSpec(var=var, equals=raw.get("equals"))


def _parse_binding_spec(raw: Any) -> BindingSpec:
    if not isinstance(raw, dict):
        raise ValueError("BindingSpec must be an object")
    from_item = str(raw.get("from_agent_item_id", "")).strip()
    from_var = str(raw.get("from_var", "")).strip()
    to_item = str(raw.get("to_agent_item_id", "")).strip()
    to_var = str(raw.get("to_var", "")).strip()
    if not (from_item and from_var and to_item and to_var):
        raise ValueError("BindingSpec requires from_agent_item_id, from_var, to_agent_item_id, to_var")
    return BindingSpec(
        from_agent_item_id=from_item,
        from_var=from_var,
        to_agent_item_id=to_item,
        to_var=to_var,
    )


def _parse_ui_spec(raw: Any) -> UiPlacementSpec:
    if not isinstance(raw, dict):
        raise ValueError("UiPlacementSpec must be an object")
    lane_index = raw.get("lane_index")
    order = raw.get("order")
    if lane_index is None or order is None:
        raise ValueError("UiPlacementSpec requires lane_index and order")
    return UiPlacementSpec(
        lane_index=int(lane_index),
        order=int(order),
        x=None if raw.get("x") is None else int(raw.get("x")),
        y=None if raw.get("y") is None else int(raw.get("y")),
    )


def _parse_agent_item_spec(raw: Any) -> AgentItemSpec:
    if not isinstance(raw, dict):
        raise ValueError("AgentItemSpec must be an object")
    item_id = str(raw.get("id", "")).strip()
    agent = str(raw.get("agent", "")).strip()
    if not item_id:
        raise ValueError("AgentItemSpec missing required field 'id'")
    if not agent:
        raise ValueError("AgentItemSpec missing required field 'agent'")
    when = _parse_when_spec(raw["when"]) if raw.get("when") is not None else None
    bindings = [_parse_binding_spec(b) for b in raw.get("bindings", []) or []]
    ui = _parse_ui_spec(raw["ui"]) if raw.get("ui") is not None else None
    return AgentItemSpec(id=item_id, agent=agent, when=when, bindings=bindings, ui=ui)


def _parse_lane_spec(raw: Any) -> LaneSpec:
    if not isinstance(raw, dict):
        raise ValueError("LaneSpec must be an object")
    items = [_parse_agent_item_spec(item) for item in raw.get("items", []) or []]
    return LaneSpec(items=items)


def _parse_graph_spec(raw: Any) -> GraphSpec:
    if not isinstance(raw, dict):
        raise ValueError("GraphSpec must be an object")
    lanes = [_parse_lane_spec(l) for l in raw.get("lanes", []) or []]
    ctx_bindings_raw = raw.get("__ctx_bindings")
    if ctx_bindings_raw is None:
        ctx_bindings_raw = raw.get("ctx_bindings")
    ctx_bindings = [_parse_binding_spec(b) for b in ctx_bindings_raw or []]
    return GraphSpec(lanes=lanes, ctx_bindings=ctx_bindings)


def agent_spec_from_dict(raw: Dict[str, Any]) -> AgentSpec:
    if any(key in raw for key in ("steps", "children", "lanes")) and "kind" not in raw:
        raise ValueError("unsupported legacy format")

    name = str(raw.get("name", "")).strip()
    if not name:
        raise ValueError("AgentSpec requires 'name'")
    title_ua_raw = raw.get("title_ua")
    title_ua = name if title_ua_raw is None or str(title_ua_raw).strip() == "" else str(title_ua_raw)
    description_ua = raw.get("description_ua")
    if description_ua is not None:
        description_ua = str(description_ua)
    kind = raw.get("kind")
    if kind not in ("atomic", "composite"):
        raise ValueError("AgentSpec.kind must be 'atomic' or 'composite'")
    executor = raw.get("executor") if kind == "atomic" else None
    if kind == "atomic" and executor not in ("llm", "python", "shell"):
        raise ValueError("Atomic agent requires executor in ['llm','python','shell']")
    if kind == "composite" and raw.get("executor"):
        raise ValueError("Composite agent must not define executor")

    inputs = [_parse_var_spec(v) for v in raw.get("inputs", []) or []]
    locals_vars = [_parse_local_var_spec(v) for v in raw.get("locals", []) or []]
    outputs = [_parse_var_spec(v) for v in raw.get("outputs", []) or []]
    ensure_stop_flag(inputs, locals_vars)
    _validate_unique_names(inputs, locals_vars, outputs)
    graph = _parse_graph_spec(raw["graph"]) if kind == "composite" else None
    if kind == "composite" and graph is None:
        raise ValueError("Composite agent requires 'graph'")

    return AgentSpec(
        name=name,
        title_ua=title_ua,
        description_ua=description_ua,
        kind=kind,  # type: ignore[arg-type]
        executor=executor,  # type: ignore[arg-type]
        inputs=inputs,
        locals=locals_vars,
        outputs=outputs,
        graph=graph,
    )


def _validate_unique_names(
    inputs: List[VarSpec], locals_vars: List[LocalVarSpec], outputs: List[VarSpec]
) -> None:
    for label, items in (
        ("input", [var.name for var in inputs]),
        ("local", [var.name for var in locals_vars]),
        ("output", [var.name for var in outputs]),
    ):
        duplicates: List[str] = []
        seen = set()
        for name in items:
            if name in seen and name not in duplicates:
                duplicates.append(name)
            seen.add(name)
        if duplicates:
            dup_str = ", ".join(sorted(duplicates))
            raise ValueError(f"Duplicate {label} variable names are not allowed: {dup_str}")


def _varspec_to_dict(var: VarSpec) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"name": var.name}
    if var.type is not None:
        payload["type"] = var.type
    if var.default is not None:
        payload["default"] = var.default
    return payload


def _localvar_to_dict(var: LocalVarSpec) -> Dict[str, Any]:
    return {"name": var.name, "value": var.value}


def _when_to_dict(when: WhenSpec) -> Dict[str, Any]:
    return {"var": when.var, "equals": when.equals}


def _binding_to_dict(binding: BindingSpec) -> Dict[str, Any]:
    return {
        "from_agent_item_id": binding.from_agent_item_id,
        "from_var": binding.from_var,
        "to_agent_item_id": binding.to_agent_item_id,
        "to_var": binding.to_var,
    }


def _ui_to_dict(ui: UiPlacementSpec) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"lane_index": ui.lane_index, "order": ui.order}
    if ui.x is not None:
        payload["x"] = ui.x
    if ui.y is not None:
        payload["y"] = ui.y
    return payload


def _agent_item_to_dict(item: AgentItemSpec) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "id": item.id,
        "agent": item.agent,
        "bindings": [_binding_to_dict(b) for b in item.bindings],
    }
    if item.when:
        payload["when"] = _when_to_dict(item.when)
    if item.ui:
        payload["ui"] = _ui_to_dict(item.ui)
    return payload


def _lane_to_dict(lane: LaneSpec) -> Dict[str, Any]:
    return {"items": [_agent_item_to_dict(item) for item in lane.items]}


def agent_spec_to_dict(spec: AgentSpec) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "name": spec.name,
        "title_ua": spec.title_ua,
        "description_ua": spec.description_ua,
        "kind": spec.kind,
        "inputs": [_varspec_to_dict(v) for v in spec.inputs],
        "locals": [_localvar_to_dict(v) for v in spec.locals],
        "outputs": [_varspec_to_dict(v) for v in spec.outputs],
    }
    if spec.kind == "atomic":
        payload["executor"] = spec.executor
    if spec.kind == "composite" and spec.graph:
        payload["graph"] = {
            "lanes": [_lane_to_dict(lane) for lane in spec.graph.lanes],
        }
        if spec.graph.ctx_bindings:
            payload["graph"]["__ctx_bindings"] = [_binding_to_dict(b) for b in spec.graph.ctx_bindings]
    return payload


__all__ = [
    "AgentSpec",
    "AgentItemSpec",
    "BindingSpec",
    "GraphSpec",
    "LaneSpec",
    "LocalVarSpec",
    "UiPlacementSpec",
    "VarSpec",
    "WhenSpec",
    "STOP_FLAG_VAR",
    "ensure_stop_flag",
    "agent_spec_from_dict",
    "agent_spec_to_dict",
]
