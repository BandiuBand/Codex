from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class VarDecl:
    """Опис змінної агента."""

    name: str
    type: str
    required: bool = False


@dataclass
class Link:
    """Зв’язок між двома змінними (адресами)."""

    src: str
    dst: str


@dataclass
class ChildRef:
    """Посилання на дочірній агент усередині composite-агента."""

    id: str
    ref: str
    run_if: Optional[str] = None


@dataclass
class Lane:
    """Вертикальна смуга з дочірніми агентами."""

    id: str
    agents: List[str] = field(default_factory=list)


@dataclass
class Agent:
    """Єдина модель агента."""

    id: str
    name: str
    description: Optional[str]
    inputs: List[VarDecl] = field(default_factory=list)
    locals: List[VarDecl] = field(default_factory=list)
    outputs: List[VarDecl] = field(default_factory=list)
    children: Dict[str, ChildRef] = field(default_factory=dict)
    lanes: List[Lane] = field(default_factory=list)
    links: List[Link] = field(default_factory=list)

    def is_atomic(self) -> bool:
        return not self.children and not self.lanes

    def child_ids(self) -> List[str]:
        return list(self.children.keys())

    def all_vars(self) -> Dict[str, VarDecl]:
        all_vars: Dict[str, VarDecl] = {}
        for decl in [*self.inputs, *self.locals, *self.outputs]:
            all_vars[decl.name] = decl
        return all_vars


AddressValue = Any
