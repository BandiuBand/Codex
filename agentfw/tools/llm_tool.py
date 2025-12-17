from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from agentfw.llm.base import DummyLLMClient, LLMClient
from agentfw.llm.json_extract import extract_first_json


@dataclass
class LLMTool:
    llm_client: LLMClient = field(default_factory=DummyLLMClient)
    parse_json: bool = True

    def run(self, variables: Dict[str, Any]) -> Dict[str, Any]:
        prompt_template = str(variables.get("prompt", ""))
        prompt = prompt_template.format(**variables)
        options_raw = variables.get("options", {})
        options = options_raw if isinstance(options_raw, dict) else {}
        output_text = self.llm_client.generate(prompt, **options)
        result: Dict[str, Any] = {"output_text": output_text}
        if self.parse_json:
            parsed, reason = extract_first_json(output_text)
            result["output_json"] = parsed
            if reason:
                result["json_error"] = reason
        return result


__all__ = ["LLMTool"]
