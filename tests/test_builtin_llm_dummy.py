from __future__ import annotations

from agentfw.runtime.engine import ExecutionEngine


def test_llm_dummy_outputs_text_and_error() -> None:
    engine = ExecutionEngine()
    state = engine.run_to_completion(
        "std.llm_json",
        input_json={"prompt": "{}"},
    )

    assert "$out.output_text" not in state.out  # outputs exposed without $out prefix
    assert "output_text" in state.out
    assert isinstance(state.out.get("parsed_json"), (dict, list))
