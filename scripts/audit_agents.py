#!/usr/bin/env python3
"""Audit agent YAML definitions for risky patterns.

Scans the ``agents`` directory for YAML files and reports potential
black-box behavior, hardcoded infrastructure, implicit control flow, and
global LLM configuration usage. Results are written to
``reports/agents_audit.json`` and ``reports/agents_audit.md``.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Dict, Any


Severity = str


@dataclass
class DetectionRule:
    id: str
    description: str
    severity: Severity
    keywords: List[str]
    regexes: List[re.Pattern[str]]

    def scan(self, content: str) -> List[str]:
        matches: List[str] = []
        lowered = content.lower()
        for keyword in self.keywords:
            if keyword.lower() in lowered:
                matches.append(f"keyword:{keyword}")
        for pattern in self.regexes:
            for found in pattern.findall(content):
                snippet = found if isinstance(found, str) else " ".join(found)
                matches.append(f"match:{snippet}")
        return matches


SEVERITY_ORDER: Dict[Severity, int] = {"HIGH": 3, "MED": 2, "LOW": 1, "INFO": 0}


def build_rules() -> List[DetectionRule]:
    url_regex = re.compile(r"https?://[^\s\"']+")
    ip_regex = re.compile(r"(?:\b\d{1,3}\.){3}\d{1,3}(?::\d+)?")
    control_flow_regex = re.compile(r"\b(if|else|elseif|switch|branch|branches|condition|when|on_success|on_failure|fallback)\b", re.IGNORECASE)
    llm_config_regex = re.compile(r"\b(model|temperature|max_tokens|llm_config|executor:\s*llm)\b", re.IGNORECASE)
    black_box_regex = re.compile(r"\bblack[- ]?box|opaque|magic|delegate\b", re.IGNORECASE)

    return [
        DetectionRule(
            id="hardcoded_infrastructure",
            description="Embedded URLs, IPs, or hostnames that may indicate hardcoded infrastructure.",
            severity="HIGH",
            keywords=["localhost:"],
            regexes=[url_regex, ip_regex],
        ),
        DetectionRule(
            id="implicit_control_flow",
            description="Implicit branching or side-effect driven control flow cues.",
            severity="MED",
            keywords=["goto", "jump"],
            regexes=[control_flow_regex],
        ),
        DetectionRule(
            id="global_llm_config",
            description="Global or shared LLM configuration that may bypass per-call controls.",
            severity="MED",
            keywords=["executor: llm", "llm:"],
            regexes=[llm_config_regex],
        ),
        DetectionRule(
            id="black_box_patterns",
            description="Mentions of opaque or delegated logic that obscures behavior.",
            severity="LOW",
            keywords=["black box", "opaque", "delegate", "magic"],
            regexes=[black_box_regex],
        ),
    ]


def calculate_agent_severity(findings: Iterable[Dict[str, Any]]) -> Severity:
    severity_level = 0
    selected: Severity = "INFO"
    for finding in findings:
        level = SEVERITY_ORDER.get(finding["severity"], 0)
        if level > severity_level:
            severity_level = level
            selected = finding["severity"]
    return selected


def audit_agent(path: Path, rules: List[DetectionRule]) -> Dict[str, Any]:
    content = path.read_text(encoding="utf-8", errors="ignore")
    findings = []
    for rule in rules:
        matches = rule.scan(content)
        if matches:
            findings.append({
                "id": rule.id,
                "description": rule.description,
                "severity": rule.severity,
                "matches": sorted(set(matches)),
            })
    agent_severity = calculate_agent_severity(findings)
    return {
        "name": path.stem,
        "path": str(path.relative_to(path.parents[2])),
        "severity": agent_severity,
        "findings": findings,
    }


def markdown_report(data: Dict[str, Any]) -> str:
    lines = ["# Agents Audit", "", f"Generated: {data['summary']['generated_at']} UTC", ""]
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total agents: {data['summary']['total_agents']}")
    for severity, count in data["summary"]["severity_counts"].items():
        lines.append(f"- {severity.title()} findings: {count}")
    lines.append("")

    grouped: Dict[Severity, List[Dict[str, Any]]] = {s: [] for s in SEVERITY_ORDER}
    for agent in data["agents"]:
        grouped.setdefault(agent["severity"], []).append(agent)

    for severity in sorted(grouped.keys(), key=lambda s: -SEVERITY_ORDER.get(s, 0)):
        agents = grouped.get(severity) or []
        lines.append(f"## {severity} ({len(agents)})")
        lines.append("")
        if not agents:
            lines.append("- None")
            lines.append("")
            continue
        for agent in sorted(agents, key=lambda a: a["name"]):
            lines.append(f"- **{agent['name']}** (`{agent['path']}`)")
            if not agent["findings"]:
                lines.append("  - No findings")
            for finding in agent["findings"]:
                match_preview = ", ".join(finding["matches"])
                lines.append(f"  - {finding['id']}: {finding['description']} ({finding['severity']})")
                lines.append(f"    - Matches: {match_preview}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_summary(agents: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts: Dict[Severity, int] = {s: 0 for s in SEVERITY_ORDER}
    for agent in agents:
        counts[agent["severity"]] = counts.get(agent["severity"], 0) + 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_agents": len(agents),
        "severity_counts": counts,
    }


def run_audit(root: Path) -> Dict[str, Any]:
    agents_dir = root / "agents"
    if not agents_dir.is_dir():
        raise SystemExit(f"Agents directory not found under {root}")

    rules = build_rules()
    agents = []
    for path in sorted(agents_dir.glob("*.yaml")):
        agents.append(audit_agent(path, rules))

    summary = build_summary(agents)
    return {"summary": summary, "agents": agents}


def persist_reports(root: Path, data: Dict[str, Any]) -> None:
    reports_dir = root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    json_path = reports_dir / "agents_audit.json"
    md_path = reports_dir / "agents_audit.md"

    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(markdown_report(data), encoding="utf-8")


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit agent YAML definitions for risky patterns.")
    parser.add_argument(
        "root",
        nargs="?",
        default=Path.cwd(),
        type=Path,
        help="Repository root (default: current directory)",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    root = args.root.resolve()
    data = run_audit(root)
    persist_reports(root, data)


if __name__ == "__main__":
    main()
