from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List

import yaml

from agentfw.core.agent import Agent, ChildRef, Lane, Link, VarDecl


def _parse_vardecl(data: Dict[str, Any]) -> VarDecl:
    name = str(data.get("name", "")).strip()
    var_type = str(data.get("type", "")).strip()
    if not name:
        raise ValueError("Variable name is required")
    if not var_type:
        raise ValueError(f"Variable '{name}' missing type")
    required = bool(data.get("required", False))
    return VarDecl(name=name, type=var_type, required=required)


def _parse_vardecls(values: Iterable[Dict[str, Any]]) -> List[VarDecl]:
    decls: List[VarDecl] = []
    for item in values:
        if not isinstance(item, dict):
            raise ValueError("Variable declarations must be objects")
        decls.append(_parse_vardecl(item))
    return decls


def _parse_link(data: Dict[str, Any]) -> Link:
    src = str(data.get("src", "")).strip()
    dst = str(data.get("dst", "")).strip()
    if not src or not dst:
        raise ValueError("Link requires both 'src' and 'dst'")
    return Link(src=src, dst=dst)


def _parse_child(data: Dict[str, Any]) -> ChildRef:
    child_id = str(data.get("id", "")).strip()
    ref = str(data.get("ref", "")).strip()
    if not child_id:
        raise ValueError("Child 'id' is required")
    if not ref:
        raise ValueError(f"Child '{child_id}' missing ref")
    run_if = data.get("run_if")
    if run_if is not None:
        run_if = str(run_if).strip()
    return ChildRef(id=child_id, ref=ref, run_if=run_if or None)


def _parse_lane(data: Dict[str, Any]) -> Lane:
    lane_id = str(data.get("id", "")).strip()
    if not lane_id:
        raise ValueError("Lane id is required")
    agents_data = data.get("agents", []) or []
    if not isinstance(agents_data, list):
        raise ValueError("Lane agents must be a list")
    return Lane(id=lane_id, agents=[str(a) for a in agents_data])


def agent_from_dict(data: Dict[str, Any]) -> Agent:
    if not isinstance(data, dict):
        raise ValueError("Agent definition must be a mapping")

    agent_id = str(data.get("id", "")).strip()
    if not agent_id:
        raise ValueError("Agent id is required")

    name_raw = data.get("name")
    name = str(name_raw).strip() if name_raw is not None else agent_id
    description = data.get("description")
    if description is not None:
        description = str(description)

    inputs = _parse_vardecls(data.get("inputs", []) or [])
    locals_vars = _parse_vardecls(data.get("locals", []) or [])
    outputs = _parse_vardecls(data.get("outputs", []) or [])

    children_data = data.get("children", {}) or {}
    if not isinstance(children_data, dict):
        raise ValueError("children must be a mapping")
    children: Dict[str, ChildRef] = {}
    for key, raw_child in children_data.items():
        if not isinstance(raw_child, dict):
            raise ValueError("child definitions must be objects")
        child = _parse_child({"id": key, **raw_child})
        children[child.id] = child

    lanes_data = data.get("lanes", []) or []
    if not isinstance(lanes_data, list):
        raise ValueError("lanes must be a list")
    lanes = [_parse_lane(item) for item in lanes_data]

    links_data = data.get("links", []) or []
    if not isinstance(links_data, list):
        raise ValueError("links must be a list")
    links = [_parse_link(item or {}) for item in links_data]

    return Agent(
        id=agent_id,
        name=name,
        description=description,
        inputs=inputs,
        locals=locals_vars,
        outputs=outputs,
        children=children,
        lanes=lanes,
        links=links,
    )


def load_agent(path: Path) -> Agent:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return agent_from_dict(data)


def _serialize_vardecls(decls: List[VarDecl]) -> List[Dict[str, Any]]:
    return [asdict(decl) for decl in decls]


def save_agent(path: Path, agent: Agent) -> None:
    payload: Dict[str, Any] = {
        "id": agent.id,
        "name": agent.name,
        "description": agent.description,
        "inputs": _serialize_vardecls(agent.inputs),
        "locals": _serialize_vardecls(agent.locals),
        "outputs": _serialize_vardecls(agent.outputs),
        "children": {},
        "lanes": [asdict(lane) for lane in agent.lanes],
        "links": [asdict(link) for link in agent.links],
    }

    for child_id, child in agent.children.items():
        payload["children"][child_id] = {
            "ref": child.ref,
            **({"run_if": child.run_if} if child.run_if else {}),
        }

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        yaml.safe_dump(payload, fp, sort_keys=False, allow_unicode=True)
