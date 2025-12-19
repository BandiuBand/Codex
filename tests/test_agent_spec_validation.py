import pytest

from agentfw.core.agent_spec import agent_spec_from_dict


def test_agent_spec_rejects_duplicate_variable_names() -> None:
    raw = {
        "name": "duplicate_vars",
        "title_ua": "Перевірка дублікатів",
        "kind": "atomic",
        "executor": "python",
        "inputs": [{"name": "завдання"}, {"name": "завдання"}],
        "locals": [],
        "outputs": [{"name": "результат"}],
    }

    with pytest.raises(ValueError, match="Duplicate input variable names are not allowed: завдання"):
        agent_spec_from_dict(raw)


def test_agent_spec_rejects_duplicate_locals() -> None:
    raw = {
        "name": "duplicate_locals",
        "title_ua": "Перевірка локальних",
        "kind": "atomic",
        "executor": "shell",
        "inputs": [{"name": "варіант"}],
        "locals": [{"name": "дубль", "value": "x"}, {"name": "дубль", "value": "y"}],
        "outputs": [{"name": "результат"}],
    }

    with pytest.raises(ValueError, match="Duplicate local variable names are not allowed: дубль"):
        agent_spec_from_dict(raw)
