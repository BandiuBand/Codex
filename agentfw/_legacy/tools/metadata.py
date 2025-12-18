"""Localized metadata for built-in tools."""

TOOL_META = {
    "llm": {
        "label_uk": "LLM-запит",
        "category": "LLM",
        "description_uk": "Генерує текст на основі промпту або змінної.",
        "schema": {
            "params": [
                {
                    "name": "prompt",
                    "type": "string",
                    "label_uk": "Промпт",
                    "description_uk": "Текст запиту (альтернатива prompt_var).",
                },
                {
                    "name": "prompt_var",
                    "type": "string",
                    "label_uk": "Змінна з промптом",
                    "description_uk": "Ім'я змінної зі вхідним текстом.",
                },
                {
                    "name": "options",
                    "type": "object",
                    "label_uk": "Параметри LLM",
                    "description_uk": "Додаткові опції виклику моделі.",
                },
            ],
            "returns": [
                {"name": "prompt", "type": "string", "description_uk": "Застосований промпт."},
                {
                    "name": "output_text",
                    "type": "string",
                    "description_uk": "Згенерована відповідь LLM.",
                },
            ],
        },
    },
    "agent_call": {
        "label_uk": "Запуск агента",
        "category": "керування",
        "description_uk": "Виконує інший агент і повертає його змінні.",
        "schema": {
            "params": [
                {
                    "name": "agent_name",
                    "type": "string",
                    "label_uk": "Агент",
                    "description_uk": "Ім'я агента для виклику (обов'язково).",
                },
                {
                    "name": "input_mapping",
                    "type": "object",
                    "label_uk": "Вхідні змінні",
                    "description_uk": "Відповідність ключ → змінна для передачі у дочірній агент.",
                },
                {
                    "name": "output_mapping",
                    "type": "array|object",
                    "label_uk": "Повернені змінні",
                    "description_uk": "Список або мапа змінних, які слід зберегти.",
                },
            ],
            "returns": [
                {
                    "name": "__child_run_id",
                    "type": "string",
                    "description_uk": "Ідентифікатор запущеного агента.",
                },
                {
                    "name": "__child_agent_name",
                    "type": "string",
                    "description_uk": "Ім'я запущеного агента.",
                },
                {
                    "name": "__child_finished",
                    "type": "boolean",
                    "description_uk": "Чи завершився виклик.",
                },
                {
                    "name": "__child_failed",
                    "type": "boolean",
                    "description_uk": "Чи завершився виклик з помилкою.",
                },
                {"name": "…", "type": "any", "description_uk": "Змінні з output_mapping."},
            ],
        },
    },
    "shell": {
        "label_uk": "Shell-команда",
        "category": "інфраструктура",
        "description_uk": "Запускає команду в оболонці.",
        "schema": {
            "params": [
                {
                    "name": "command",
                    "type": "string|array",
                    "label_uk": "Команда",
                    "description_uk": "Рядок або список аргументів (обов'язково).",
                },
                {
                    "name": "allow_failure",
                    "type": "boolean",
                    "label_uk": "Ігнорувати помилку",
                    "description_uk": "Дозволити ненульовий код завершення.",
                },
                {
                    "name": "cwd",
                    "type": "string",
                    "label_uk": "Каталог",
                    "description_uk": "Робочий каталог для команди.",
                },
                {
                    "name": "timeout",
                    "type": "number",
                    "label_uk": "Тайм-аут, с",
                    "description_uk": "Максимальна тривалість виконання.",
                },
                {
                    "name": "env",
                    "type": "object",
                    "label_uk": "Змінні середовища",
                    "description_uk": "Додаткові змінні середовища.",
                },
            ],
            "returns": [
                {
                    "name": "return_code",
                    "type": "number",
                    "description_uk": "Код завершення команди.",
                },
                {"name": "stdout", "type": "string", "description_uk": "Стандартний вивід."},
                {"name": "stderr", "type": "string", "description_uk": "Стандартний потік помилок."},
                {"name": "ok", "type": "boolean", "description_uk": "Чи успішно виконано."},
            ],
        },
    },
    "echo": {
        "label_uk": "Шаблонований текст",
        "category": "debug",
        "description_uk": "Рендерить текст із підстановкою змінних.",
        "schema": {
            "params": [
                {
                    "name": "text",
                    "type": "string",
                    "label_uk": "Текст",
                    "description_uk": "Шаблон із плейсхолдерами {var}.",
                }
            ],
            "returns": [
                {"name": "output_text", "type": "string", "description_uk": "Згенерований текст."}
            ],
        },
    },
    "math_add": {
        "label_uk": "Складання чисел",
        "category": "utility",
        "description_uk": "Додає два числа зі змінних стану.",
        "schema": {
            "params": [
                {
                    "name": "a_var",
                    "type": "string",
                    "label_uk": "Перше число",
                    "description_uk": "Назва змінної з першим доданком.",
                },
                {
                    "name": "b_var",
                    "type": "string",
                    "label_uk": "Друге число",
                    "description_uk": "Назва змінної з другим доданком.",
                },
            ],
            "returns": [
                {"name": "result", "type": "number", "description_uk": "Сума a_var та b_var."}
            ],
        },
    },
    "accept_validator": {
        "label_uk": "Безумовне схвалення",
        "category": "валідація",
        "description_uk": "Повертає accept із повідомленням.",
        "schema": {
            "params": [
                {
                    "name": "message",
                    "type": "string",
                    "label_uk": "Повідомлення",
                    "description_uk": "Текст для результату валідації.",
                },
                {
                    "name": "patch",
                    "type": "object",
                    "label_uk": "Патч",
                    "description_uk": "Опційні зміни стану, що додаються до результату.",
                },
            ],
            "returns": [
                {
                    "name": "validation",
                    "type": "object",
                    "description_uk": "Об'єкт {status: 'accept', message, patch?}.",
                }
            ],
        },
    },
    "flaky": {
        "label_uk": "Нестабільний виклик",
        "category": "debug",
        "description_uk": "Лічить спроби та повертає номер поточної.",
        "schema": {
            "params": [
                {
                    "name": "counter_var",
                    "type": "string",
                    "label_uk": "Лічильник",
                    "description_uk": "Назва змінної лічильника (за замовчуванням __flaky_attempt).",
                },
                {
                    "name": "message",
                    "type": "string",
                    "label_uk": "Повідомлення",
                    "description_uk": "Базовий текст для відповіді.",
                },
                {
                    "name": "reset",
                    "type": "boolean",
                    "label_uk": "Скинути",
                    "description_uk": "Перед виконанням обнулити лічильник.",
                },
            ],
            "returns": [
                {"name": "attempt", "type": "number", "description_uk": "Поточний номер спроби."},
                {
                    "name": "message",
                    "type": "string",
                    "description_uk": "Повідомлення з номером спроби.",
                },
            ],
        },
    },
    "attempt_threshold_validator": {
        "label_uk": "Поріг спроб",
        "category": "валідація",
        "description_uk": "Приймає або просить повтор, доки не досягнуто порогу.",
        "schema": {
            "params": [
                {
                    "name": "accept_after",
                    "type": "number",
                    "label_uk": "Прийняти після",
                    "description_uk": "Поріг номера спроби для accept.",
                },
                {
                    "name": "force_fail",
                    "type": "boolean|string",
                    "label_uk": "Примусова помилка",
                    "description_uk": "Якщо істина – завжди fail.",
                },
                {
                    "name": "fail_message",
                    "type": "string",
                    "label_uk": "Текст помилки",
                    "description_uk": "Повідомлення для примусової помилки.",
                },
            ],
            "returns": [
                {
                    "name": "validation",
                    "type": "object",
                    "description_uk": "Об'єкт {status: accept|retry|fail, message}.",
                }
            ],
        },
    },
}

__all__ = ["TOOL_META"]
