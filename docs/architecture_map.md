# Мапа архітектури: keep vs legacy

## Keep (новий стек)
- `agentfw/core/agent_spec.py` — єдина модель агента (atomic/composite), парсинг/серіалізація.
- `agentfw/io/agent_yaml.py` — збереження та завантаження AgentSpec з YAML.
- `agentfw/runtime/engine.py` — виконання агента/воркфлоу, lane-барʼєри, LLM-параметри тільки через змінні агента.
- `agentfw/web/*` — HTTP-сервер + статичний UI (canva, lanes, drag&drop, модалка запуску).
- `agents/*` — актуальні YAML-агенти, зокрема `llm_ollama`, `prompt_builder`, `output_collector`, `llm_prompt_chain`.
- `demo/simple_agent_demo.py` — демонстрація запуску YAML-агентів через ExecutionEngine без глобальних конфігів.

## Legacy (ізольовано в `_legacy`)
- `agentfw/_legacy/tools/*` — колишні тулси (`BaseTool`, `LLMTool`, shell/python/builtin). Старі шляхи `agentfw/tools/*` лишилися як заглушки, що падають з RuntimeError.
- `agentfw/_legacy/runtime/builtins.py` — попередній реєстр builtin-агентів; старий шлях теж заглушка.
- `agentfw/_legacy/core/models.py` — стара модель агентів/степів; на старому шляху RuntimeError, перехід тільки на AgentSpec.
- `agentfw/_legacy/config/*` — усі глобальні конфіги/лоадери (LLMConfig, env/файлові настройки). `agentfw/config/*` тепер заглушки.
- Інші згадки старого API (registry/tools/examples) вважаються legacy і мають не використовуватися в нових фічах.

## Політика використання
- Новий код повинен оперувати лише AgentSpec + ExecutionEngine + YAML агентами.
- Будь-які імпорти з `agentfw._legacy` або старих шляхів-заглушок слугують сигналом для видалення/міграції.
- LLM конфіг передається виключно змінними агента (host/model/temperature), без глобальних файлів чи налаштувань.
