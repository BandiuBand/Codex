Ціль

Зробити єдину модель Agent (без node/tool/workflow) з виконанням “смугами” (lanes) та можливістю композиції з маленьких агентів. Усі “налаштування” — тільки змінні (inputs/locals/outputs) і зв’язки між ними. Default-значення через змінні, не через config.

0) Заборони (щоб не з’явився хаос)

❌ Не вводити класи/сутності Node, Tool, Workflow.

❌ Не робити “config/prompt/code/command” окремими налаштуваннями.

✅ Усе — Agent.

✅ “LLM/Python/Shell” — це вбудовані стандартні агенти (library agents), але UI бачить їх як звичайні агенти з портами.

1) Модель Agent (єдина схема)
1.1. Файл

Створити: agentfw/core/agent.py

1.2. Dataclasses/typing

Описати:

VarDecl

Link

ChildRef

Lane

Agent

VarDecl

Поля:

name: str

type: str (мінімум: string|int|float|bool|object|array)

required: bool = False

Link

Зв’язок “змінна → змінна” (drag&drop в UI)

src: str

dst: str

Формат адрес:

$in.<var> — input агента

$local.<var> — внутрішня змінна агента

$out.<var> — output агента

<child_id>.$in.<var> — input дочірнього агента

<child_id>.$local.<var> — local дочірнього агента

<child_id>.$out.<var> — output дочірнього агента

ChildRef

id: str — локальний id інстансу всередині поточного агента

ref: str — id агента, який викликається (посилання на інший YAML-агент)

run_if: str | None — умова (простий expression string), опційно

run_if — звичайний рядок-вираз, який оцінюється (див. п.4).

Lane

id: str

agents: list[str] — список child.id, які лежать у цій вертикальній смузі

Agent

id: str

name: str

description: str | None

inputs: list[VarDecl]

locals: list[VarDecl]

outputs: list[VarDecl]

children: dict[str, ChildRef] (ключ = child.id)

lanes: list[Lane]

links: list[Link]

Правило: агент може бути:

atomic: children пустий і lanes пустий → виконується через built-in реалізацію за agent.id

composite: має children і lanes

2) Зберігання агентів (YAML)
2.1. Loader/Saver

Створити: agentfw/io/agent_yaml.py

Функції:

load_agent(path: Path) -> Agent

save_agent(path: Path, agent: Agent) -> None

2.2. Розміщення

Каталог агентів: agents/
1 YAML = 1 агент.

3) Реєстр вбудованих (standard) агентів
3.1. Ціль

“LLM/Python/Shell/Condition/Render/Merge” реалізуються як built-in за agent.id, але в YAML і UI це звичайні агенти з портами.

3.2. Реєстр

Створити: agentfw/runtime/builtins.py

BuiltinAgentRegistry:

register(agent_id: str, fn: Callable[[ExecutionContext], dict])

has(agent_id: str) -> bool

run(agent_id: str, ctx: ExecutionContext) -> dict

3.3. Мінімально необхідні built-in агенти (обов’язково)

std.llm_json
Inputs:

$in.prompt (string)

$in.options (object, optional)
Outputs:

$out.output_text (string)

$out.parsed_json (object)

$out.json_error (string)

std.python
Inputs:

$in.code (string)

$in.vars (object, optional) — поточні змінні (може бути весь ctx)
Outputs:

$out.patch (object) — словник змінних для мерджу в контекст

$out.stdout (string)

$out.error (string)

std.shell
Inputs:

$in.command (string або array)

$in.cwd (string, optional)

$in.timeout (int, optional)
Outputs:

$out.return_code (int)

$out.stdout (string)

$out.stderr (string)

$out.ok (bool)

std.condition
Inputs:

$in.expr (string)
Outputs:

$out.value (bool)

std.condition потрібен як “умова агентом” якщо користувач хоче робити умови через блок.

4) Механізм умов run_if (без LLM магії)
4.1. Формат

run_if — це expression string, наприклад:

$local.needs_planning == true

childA.$out.ok == true

($local.i < 10) and ($local.flag == true)

4.2. Реалізація

Створити: agentfw/runtime/expr.py

Функція:

eval_expr(expr: str, resolver: Callable[[str], Any]) -> bool

Обмеження безпеки:

не використовувати eval напряму.

реалізувати малий парсер (або дозволити тільки:

== != < <= > >=

and or not

дужки

true/false/числа/рядки

змінні через address resolver)

5) Виконання агента (Engine)
5.1. Файл

Оновити/переробити: agentfw/runtime/engine.py

5.2. Публічний метод

run_to_completion(agent_id: str, input_json: dict) -> ExecutionState

5.3. Семантика виконання

Створюємо ExecutionContext з:

$in.* з input_json

$local.* пусто

$out.* пусто

Якщо агент atomic:

викликаємо BuiltinAgentRegistry.run(agent.id, ctx)

результати кладемо в $out.* і/або $local.* (див. п.6)

завершуємо

Якщо agent composite:

обходимо lanes зліва направо

у lane беремо список child_ids

для кожного child:

якщо є run_if → оцінити (через eval_expr)

якщо false → child пропускається і НЕ блокує lane

якщо true → виконати child

lane завершується коли завершились усі активні child

після кожного child:

застосувати links (див. п.6) / оновити контекст

Після усіх lanes:

зібрати $out.* і повернути результат

5.4. Паралельність

На старті дозволено “псевдо-паралельність” (послідовно), але barrier-логіка lane має бути правильною.
Якщо робитимете паралельність — використовувати thread pool, але це не обов’язково для MVP.

6) Links: єдина система “перетягування змінних”
6.1. Вимога

Default-значення не існує.
Щоб подати “константу/текст/код” у input, користувач робить:

$local.prompt_text -> child.$in.prompt
або

$in.task_text -> child.$in.task_text

Тобто потрібна можливість задавати $local.* вручну при запуску або через окремий built-in агент “set”.

6.2. Як задавати значення locals

Додати в API запуску (див. п.7) поле:

locals_json — словник $local значень на старті.

7) HTTP API (для UI)
7.1. Список агентів

GET /api/agents

Response:

{
  "agents": [
    { "id": "task_complexity_classifier", "name": "..." },
    { "id": "std.llm_json", "name": "LLM → JSON" }
  ]
}

7.2. Отримати одного агента

GET /api/agents/{agent_id}
Повертає повний YAML у JSON-формі (структура Agent).

7.3. Зберегти агента

PUT /api/agents/{agent_id}
Body = структура Agent, сервер зберігає у agents/{agent_id}.yaml.

7.4. Запуск агента (форма “input/output”)

POST /api/agents/run

Request:

{
  "agent_id": "task_complexity_classifier",
  "input_json": { "task_text": "..." },
  "locals_json": { "prompt_text": "..." } 
}


Response:

{
  "agent_id": "...",
  "run_id": "...",
  "finished": true,
  "failed": false,
  "out": { ... },     
  "locals": { ... },  
  "trace": [ ... ]    
}

8) Тести (мінімум)

Створити:

tests/test_links.py — перевірити, що $local.x -> child.$in.y працює

tests/test_run_if.py — пропуск child не блокує lane

tests/test_builtin_llm_dummy.py — dummy LLM повертає валідний JSON (для CI)

tests/test_agent_run_api.py — basic run endpoint

Acceptance Criteria (бекенд)

 В коді немає Node/Tool/Workflow моделей.

 Агент описується одним YAML форматом.

 std.llm_json, std.python, std.shell, std.condition працюють як built-in агенти.

 lanes виконуються з barrier-логікою.

 links працюють для $in/$local/$out і child.* адрес.

 Є API: list/get/put/run.