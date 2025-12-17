from agentfw.llm.json_extract import extract_first_json


def test_json_extract_fenced_codeblock() -> None:
    text = """
    початок
    ```json
    {"a": 1, "b": 2}
    ```
    кінець
    """

    parsed, reason = extract_first_json(text)

    assert parsed == {"a": 1, "b": 2}
    assert reason is None


def test_json_extract_inline_object() -> None:
    parsed, reason = extract_first_json("префікс {\"value\": true} суфікс")

    assert parsed == {"value": True}
    assert reason is None
