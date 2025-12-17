# TASK_BACKEND_V2 — “Єдиний клас Agent + змінні + lane-виконання + JSON з LLM”
Гілка: main2
Ціль: backend має підтримати єдину модель “Agent” (atomic/composite) + змінні + зв’язки змінних + послідовні вертикальні “lane” + запуск агента з UI.

## 0) Жорсткі правила (НЕ обговорюється)
1) НІЯКИХ сутностей “tool/node/step” у зовнішній моделі. Зовні існує ТІЛЬКИ Agent.
2) Workflow = Agent (composite). Atomic = Agent (executor: llm/python/shell).
3) Вхід/вихід/локальні змінні — це перші сутності.
4) Гілки/цикли — реалізуються умовами запуску агента + можливістю викликати самого себе (composite -> містить agentRef на себе).

## 1) Новий контракт даних (AgentSpec)
Додати модуль: `agentfw/core/agent_spec.py`

### AgentSpec (Python dataclass + (de)serialization)
Поля:
- `name: str` (технічне ім’я, ключ)
- `title_ua: str` (для UI, українською; якщо пусто — fallback на name)
- `description_ua: str` (опціонально)
- `kind: Literal["atomic","composite"]`
- `executor: Optional[Literal["llm","python","shell"]]` (тільки якщо kind="atomic")
- `inputs: list[VarSpec]`
- `locals: list[LocalVarSpec]`
- `outputs: list[VarSpec]`
- `graph: Optional[GraphSpec]` (тільки якщо kind="composite")

VarSpec:
- `name: str`

LocalVarSpec:
- `name: str`
- `value: str`  (рядок; UI редагує як текст)

GraphSpec:
- `lanes: list[LaneSpec]`  (виконання зліва -> направо)
LaneSpec:
- `items: list[AgentItemSpec]`

AgentItemSpec:
- `id: str` (uuid)
- `agent: str` (ім’я агента, якого викликаємо)
- `when: Optional[WhenSpec]`  (умова запуску; якщо false -> SKIP і НЕ блокує lane barrier)
- `bindings: list[BindingSpec]` (зв’язки змінних)
- `ui: Optional[UiPlacementSpec]` (координати для фронта)

WhenSpec (мінімально):
- `var: str` (ім’я змінної)
- `equals: Union[str,bool,int,float,None]` (просте порівняння)
(Далі можна розширити, але зараз мінімум.)

BindingSpec:
- `from_agent_item_id: str`  (джерело; спеціальне значення "__CTX__" означає “з глобального контексту/локальних”)
- `from_var: str`            (ім’я змінної-джерела)
- `to_agent_item_id: str`    (цільовий item id)
- `to_var: str`              (ім’я input змінної цільового агента)

UiPlacementSpec:
- `lane_index: int`
- `order: int` (порядок в lane)
- `x: int`, `y: int` (опційно, якщо фронт робить drag по площині)

## 2) Завантаження/збереження YAML
Знайти поточний loader/saver агентів (в репо він вже є, бо `agents/` використовується).
Оновити так, щоб:
- YAML/JSON агента мапився 1-в-1 на AgentSpec.
- Старі формати (якщо є) або:
  a) конвертуються в новий формат (краще), або
  b) відкидаються з явною помилкою “unsupported legacy format”.
Вимога: UI має працювати тільки з новим AgentSpec.

## 3) Виконання (ExecutionEngine)
Файл: `agentfw/runtime/engine.py`

Додати/доробити:
- `run_to_completion(agent_name: str, input_json: dict) -> ExecutionState`:
  - Завантажує AgentSpec.
  - Створює ExecutionContext з глобальними vars (input_json).
  - Якщо kind="atomic" -> виконує atomic executor.
  - Якщо kind="composite" -> виконує lanes.

### 3.1) Lane semantics
Для кожної lane зліва направо:
- Обчислити список item’ів в lane у `order`.
- Для кожного item:
  - Якщо `when` задано і умова false -> SKIP (не виконуємо, не блокує lane)
  - Інакше виконуємо item:
    - Підготувати child_input через bindings:
      - Кожен input цільового агента може отримувати значення:
        - або з output іншого item (binding from_agent_item_id),
        - або з "__CTX__" (глобальні vars + locals).
    - Запустити `run_to_completion(child_agent_name, child_input)`.
    - Після завершення — записати outputs child в глобальний контекст:
      - за іменами outputs агента (same name) у ctx.variables
- Barrier: наступна lane стартує тільки після того, як всі НЕ-skipped items цієї lane завершені.

Паралельність: поки що можна виконувати послідовно, але API/структура мають не заважати паралельному виконанню в майбутньому.

### 3.2) Цикли
Дозволити composite графу мати item, який викликає агента з тим самим ім’ям (self-call).
Потрібен захист від нескінченності:
- `max_total_steps` у engine config (наприклад 10_000) — якщо перевищено, падати з помилкою.
- `max_depth` рекурсії (наприклад 50).

## 4) Atomic executors
### 4.1) LLM executor
Файл: `agentfw/tools/llm_tool.py` (або де зараз `LLMTool` — у вас він є)
Доробити LLMTool так, щоб:
- На вхід отримував prompt (через template з ctx).
- Повертав:
  - `output_text: str`
  - `output_json: Optional[dict]` (якщо увімкнено parse_json)

Додати модуль: `agentfw/llm/json_extract.py`
Функція: `extract_first_json(text: str) -> tuple[Optional[dict], Optional[str]]`
- Шукає JSON:
  - або всередині ```json ... ```
  - або перший валідний об’єкт `{...}` / масив `[...]` у тексті
- Якщо parse успішний -> dict/list (але в змінні кладемо dict; list дозволено під ключем)
- Якщо ні -> повертає None + reason.

### 4.2) Python executor
Файл: `agentfw/tools/python_tool.py`
Мінімум:
- Виконує код (string) в sandboxed locals dict (ctx.vars доступні тільки через явне прокидання)
- Повертає `output_vars: dict` (тільки дозволені keys, наприклад ті що оголошені outputs)

### 4.3) Shell executor
Файл: `agentfw/tools/shell_tool.py` (у вас є `ShellTool`)
- Додати whitelist параметрів (cwd, timeout, allow_failure)
- Заборонити довільні env override (або дозволити тільки явний список ключів)

## 5) Web API для UI
Модуль: `agentfw/web/api.py` (або де у вас FastAPI/Flask endpoints)

Додати endpoints:
- `GET /api/agents` -> список агентів:
  - `[ {name, title_ua, kind, inputs, outputs, locals} ]`
- `GET /api/agent/{name}` -> повний AgentSpec (json)
- `POST /api/agent/{name}` -> зберегти AgentSpec (json->yaml на диск)
- `POST /api/run/{name}` body: `{ "input": {...} }`
  -> `{ "ok": bool, "vars": {...}, "log": [...], "error": null|{...} }`

Вимога: весь UI текст українською, але API повертає `title_ua/description_ua`.

## 6) Тести (обов’язково)
Папка: `tests/`
Додати тести:
1) `test_json_extract_fenced_codeblock`
2) `test_json_extract_inline_object`
3) `test_composite_lane_barrier_and_skip`
4) `test_self_call_stops_on_max_steps`
5) `test_bindings_ctx_to_input_and_output_to_ctx`

## 7) Definition of Done
- Можна створити 3 агенти YAML:
  - `classify_task` (llm) -> outputs: `is_complex: bool`
  - `echo` (atomic python або llm) -> outputs: `text`
  - `workflow_demo` (composite) з 2 lanes:
    lane0: classify_task
    lane1: (when is_complex==false) -> echo_simple, (when is_complex==true) -> echo_plan
- `POST /api/run/workflow_demo` працює і повертає vars.
- extract_first_json працює.


## 10) Definition of Done
- Нема merge-conflict маркерів.
- `python run.py test` проходить.
- `POST /api/agents/task_classifier/run` повертає `original_task` і `is_complex` (булеве).
- Після кожного run з’являється `runs/<run_id>/state.json` і `trace.json`.
