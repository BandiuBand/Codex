# TASK_BACKEND.md — Codex: бекенд під модель "Є тільки Агент"

## 0) Блокери (виконати ПЕРШИМ)
### 0.1 Прибрати merge-conflict маркери
- Команда перевірки:
  - `git grep -n "<<<<<<<\\|=======\\|>>>>>>>" -- "*.py" "*.js" "*.html" "*.css"`
- Вимога:
  - у репозиторії НЕ ПОВИННО залишитися жодного `<<<<<<<`, `=======`, `>>>>>>>`.
- Додати pre-commit або CI-перевірку (можна як скрипт у `scripts/`), яка валить білд при наявності цих маркерів.

## 1) Ціль
Зробити runtime та API так, щоб:
- **Є одна сутність: Agent**
- Агент буває:
  - `atomic` (executor: `llm | python | shell`)
  - `composite` (містить схему з інших агентів, виконання "смугами" зліва-направо)
- Розгалуження/цикли — не “особливі режими”, а нормальні агенти/умови в схемі.
- Вхід/вихід/внутрішні змінні — частина агента.
- Після виконання кожного агента — серіалізація стану/трейсу в файли.

## 2) Canonical data model (тільки Agent)
### 2.1 Додати/затвердити схему AgentSpec (Python dataclasses)
**Файли:**
- `agentfw/core/agent_spec.py` (НОВИЙ)
- `agentfw/core/__init__.py` (експорт)

**Класи/поля:**
- `VarSpec`:
  - `name: str`
  - `ui_label_uk: str`
  - `description_uk: str = ""`
  - `type: str = "any"`  # "str|int|float|bool|json|any"
- `AgentSpec`:
  - `name: str`
  - `ui_title_uk: str`
  - `kind: Literal["atomic","composite"]`
  - `executor: Optional[Literal["llm","python","shell"]]`  # лише для atomic
  - `inputs: list[VarSpec]`
  - `internals: list[VarSpec]`
  - `outputs: list[VarSpec]`
  - `body_var: Optional[str]`  # ім’я внутрішньої змінної, яка містить prompt/code/command
  - `lanes: list[LaneSpec] = []`  # лише для composite
- `LaneSpec`:
  - `lane_id: str`
  - `ui_title_uk: str`
  - `items: list[LaneItemSpec]`  # виконуються паралельно в межах lane
- `LaneItemSpec`:
  - `item_id: str`
  - `agent_ref: str`  # ім’я іншого AgentSpec або self
  - `enabled_if: Optional[ConditionSpec] = None`
  - `input_bindings: dict[str,str]`   # child_input_name -> parent_var_name
  - `output_bindings: dict[str,str]`  # child_output_name -> parent_var_name
- `ConditionSpec`:
  - `mode: Literal["var_bool","agent_bool","python_expr"]`
  - `ref: str`  # var name / agent name / python expression
  - `params: dict = {}`

## 3) YAML loader/saver
### 3.1 Завантаження агентів з `agents/*.yaml`
**Файли:**
- `agentfw/io/agent_yaml.py` (НОВИЙ або переробити існуючий)
- `agentfw/io/__init__.py`

**Функції:**
- `load_agent_spec(path: Path) -> AgentSpec`
- `save_agent_spec(path: Path, spec: AgentSpec) -> None`
- `validate_agent_spec(spec: AgentSpec) -> list[str]`  # повертає список помилок

**Вимоги валідації:**
- `kind=atomic` => executor не None, body_var заданий і є у `internals`.
- `kind=composite` => lanes не порожній.
- всі `VarSpec.name` у межах агента унікальні (inputs+internals+outputs).
- bindings посилаються на існуючі змінні.
- `agent_ref` існує, або дозволено `"self"`.

## 4) Runtime engine
### 4.1 ExecutionContext/State
**Файли:**
- `agentfw/runtime/state.py` (переробити існуючий або створити)
- `agentfw/runtime/engine.py` (переробити)

**Вимоги:**
- Є `ExecutionState`:
  - `run_id: str`
  - `agent_name: str`
  - `vars: dict[str, Any]`
  - `trace: list[TraceEvent]`
- `TraceEvent` мінімум:
  - `ts`
  - `agent_name`
  - `item_id`
  - `status: started|finished|skipped|failed`
  - `inputs_snapshot`
  - `outputs_snapshot`
  - `error: Optional[str]`

### 4.2 Виконання composite агентів "смугами"
- Lanes виконуються зліва-направо.
- Всередині lane: всі `items`, у яких `enabled_if` істинний, виконуються паралельно (ThreadPool/asyncio — на вибір).
- Lane завершується, коли завершилися всі enabled items (skipped не блокує).
- Після lane переходити до наступного.

### 4.3 Atomic executors
**Файли:**
- `agentfw/runtime/executors.py` (НОВИЙ)

**Функції:**
- `run_atomic_llm(spec, state, llm_client) -> dict`
- `run_atomic_python(spec, state) -> dict`
- `run_atomic_shell(spec, state) -> dict`

**Правило body_var:**
- береться `state.vars[spec.body_var]` як шаблон
- виконується template-render `{var}` -> значення зі `state.vars`
- результат подається в executor

## 5) JSON extraction з відповіді LLM
**Файли:**
- `agentfw/utils/json_extract.py` (НОВИЙ)

**Функції:**
- `extract_first_json(text: str) -> Any`
  - підтримати:
    - ```json ... ```
    - ``` ... ```
    - inline `{...}` або `[...]`
  - якщо не знайшли валідний JSON — кинути `JsonExtractError`
- `coerce_json_object(value: Any) -> dict` (опційно)

**Використання:**
- якщо вихідна змінна atomic-LLM агента має тип `json`, то:
  - або LLM одразу повертає JSON у `output_text`,
  - або парсимо JSON і кладемо у змінну (напр. `parsed_json`).

## 6) Серіалізація в файли (після кожного run)
**Файли:**
- `agentfw/runtime/persistence.py` (НОВИЙ)

**Вимоги:**
- Створювати директорію `runs/<run_id>/`
- Писати:
  - `state.json` (vars)
  - `trace.json` (trace events)

## 7) HTTP API для фронтенду
**Файли:**
- `agentfw/web/api.py` (НОВИЙ або переробити)
- `agentfw/web/__init__.py` / `agentfw/web/server.py`

**Ендпоінти:**
- `GET /api/agents` -> список `{name, ui_title_uk, kind, executor}`
- `GET /api/agents/{name}` -> повний AgentSpec (JSON)
- `POST /api/agents/{name}/run` body: `{ "input": { ... } }`
  - response: `{ "run_id": ..., "output": {...}, "trace": [...] }`

## 8) Обов’язкові демо-агенти
**Файли (agents/):**
- `agents/task_classifier.yaml`
  - atomic llm
  - inputs: `task_text`
  - outputs: `is_complex: bool`, `original_task: str`
  - вимога: LLM ПОВЕРТАЄ JSON `{ "is_complex": true/false, "original_task": "..." }`
- `agents/py_eval.yaml`
  - atomic python
  - inputs: `code` (або body_var)
  - outputs: `result`

## 9) Тести
**Файли:**
- `tests/test_json_extract.py`
- `tests/test_engine_lanes_parallelism.py`
- `tests/test_task_classifier_contract.py` (перевіряє, що агент існує і має потрібні поля)

## 10) Definition of Done
- Нема merge-conflict маркерів.
- `python run.py test` проходить.
- `POST /api/agents/task_classifier/run` повертає `original_task` і `is_complex` (булеве).
- Після кожного run з’являється `runs/<run_id>/state.json` і `trace.json`.
