"""Localized metadata for built-in tools."""

TOOL_META = {
    "llm": {
        "label_uk": "Виклик LLM",
        "category": "LLM",
        "description_uk": "Генерує текст за допомогою локальної або зовнішньої LLM.",
    },
    "agent_call": {
        "label_uk": "Виклик іншого агента",
        "category": "керування",
        "description_uk": "Запускає інший агент і повертає його змінні.",
    },
    "shell": {
        "label_uk": "Shell-команда",
        "category": "інфраструктура",
        "description_uk": "Запускає команду в оболонці (pytest, mypy, тощо).",
    },
    "echo": {
        "label_uk": "Шаблонований текст",
        "category": "debug",
        "description_uk": "Повертає текст, підставляючи змінні стану.",
    },
    "math_add": {
        "label_uk": "Складання чисел",
        "category": "utility",
        "description_uk": "Додає два числа зі стану агента й повертає суму.",
    },
    "accept_validator": {
        "label_uk": "Безумовне схвалення",
        "category": "валідація",
        "description_uk": "Завжди повертає статус accept із повідомленням.",
    },
    "flaky": {
        "label_uk": "Нестабільний виклик",
        "category": "debug",
        "description_uk": "Інкрементує лічильник викликів та повертає номер спроби.",
    },
    "attempt_threshold_validator": {
        "label_uk": "Поріг спроб",
        "category": "валідація",
        "description_uk": "Приймає/перезапускає крок залежно від номера спроби та налаштувань.",
    },
}

__all__ = ["TOOL_META"]
