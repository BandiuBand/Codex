# Аудит legacy та “глобальних” згадок

Команди: 
- `rg "LLMConfig|from_env|ollama.*config|config.*llm" -n`
- `rg "agentfw\.tools|registry|builtin|Step|Tool" -n`
- `rg "ExecutionEngine\(" -n`

## LLMConfig / глобальні конфіги
- `agentfw/_legacy/config/settings.py`, `agentfw/_legacy/config/loader.py` — повний спадок LLMConfig та env/файлових конфігів (позначено як legacy).
- `docs/architecture_map.md` — фіксує, що конфіги винесені в `_legacy` та не використовуються новим стеком.
- `tests/test_execution_engine.py` — згадка `llm_configured` лише у новому тесті на змінні LLM (не глобальний конфіг).

## Згадки tools/registry/Step/Tool
- `examples/simple_agent_demo.py` та `agentfw/core/registry.py` — старий API з Tool/StepDefinition; наразі не використовується в основному потоці, слід мігрувати/позначити як legacy у наступних ітераціях.
- `agentfw/_legacy/tools/*`, `agentfw/_legacy/runtime/builtins.py`, `agentfw/_legacy/core/models.py`, `agentfw/_legacy/config/*` — перенесені оригінальні реалізації; старі шляхи у `agentfw/tools/*` тощо тепер заглушки з RuntimeError.
- `agentfw/persistence/state.py` та `agentfw/persistence/storage.py` ще містять Step/History артефакти попередньої моделі (кандидат на подальше винесення в legacy або переписування під AgentSpec).

## Виклики ExecutionEngine
- `demo/simple_agent_demo.py`, `tests/test_execution_engine.py`, `agentfw/web/server.py`, `agentfw/runtime/factory.py`, `examples/simple_agent_demo.py` — єдині актуальні місця створення Engine.
- Сервер тепер передає `llm_client_factory`, щоб LLM отримував параметри виключно зі змінних агента; інші виклики використовують дефолт без глобальних конфігів.
