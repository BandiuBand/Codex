import pytest

from agentfw.llm.json_utils import extract_json_from_text


def test_extracts_plain_json_block() -> None:
    parsed, error = extract_json_from_text('{"a": 1, "b": 2}')

    assert parsed == {"a": 1, "b": 2}
    assert error is None


def test_extracts_json_fenced_block() -> None:
    text = """Some intro
```json
{"foo": "bar"}
```
post"""

    parsed, error = extract_json_from_text(text)

    assert parsed == {"foo": "bar"}
    assert error is None


def test_extracts_any_fenced_block() -> None:
    parsed, error = extract_json_from_text("```[1, 2, 3]```")

    assert parsed == [1, 2, 3]
    assert error is None


def test_extracts_first_balanced_object() -> None:
    text = "header text {\"wrapped\": {\"value\": 5}} trailer"

    parsed, error = extract_json_from_text(text)

    assert parsed == {"wrapped": {"value": 5}}
    assert error is None


def test_returns_error_when_no_json_found() -> None:
    parsed, error = extract_json_from_text("just explanatory text without json")

    assert parsed is None
    assert isinstance(error, str)
    assert error
