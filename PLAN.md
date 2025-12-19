0) Цільове бачення (що має вийти)
Єдиний вхід/вихід — Chat Agent

Веб-сторінка не запускає напряму adaptive_task_agent.

Веб-сторінка шле повідомлення лише в ChatAgent.

ChatAgent:

приймає user message;

передає його в середній рівень (“оркестратор/планувальник”);

якщо потрібні уточнення — повертає питання користувачу;

якщо результат у файл — робить запис через file-agent і повертає користувачу пояснення + шлях/посилання.

“Інструменти” — теж агенти

File IO, list files, read file, write file, (опційно) python/shell — викликаються як підлеглі агенти, не “магічно”.

1) Протокол взаємодії (обов’язково стандартизувати)
1.1. Єдиний формат повідомлень між агентами

Запровадити уніфіковану структуру (JSON-схема або pydantic/java record — що у вас там):

AgentEnvelope

conversation_id

message_id

role: user | chat | agent | tool

timestamp

content: текст

attachments: список (імена файлів/шляхи/метадані)

tooling_state: що реально доступно зараз

available_agents: [ "file_list", "file_read", "file_write", "python_exec", "shell_exec", ... ]

project_root: шлях

security_mode: safe | restricted | dev

expected_output: final | question | plan | tool_call | file_written

1.2. Статуси виконання, щоб прибити “вигадування”

Усі агенти (особливо executor) мають повертати один із:

status: ok

status: blocked

status: error

Якщо blocked, обов’язково:

missing_inputs: [...] (конкретно що треба)

questions_to_user: [...] (1–5 конкретних питань)

why_blocked: ...

2) Новий Chat Agent (шлюз між UI і системою)
2.1. Функції ChatAgent

Session manager

тримає conversation_id, історію повідомлень (коротку) + посилання на файли/артефакти.

Router

передає повідомлення в “середній рівень агентів” (наприклад adaptive_task_agent або новий “OrchestratorAgent”).

Question loop

якщо прийшло status=blocked або expected_output=question, ChatAgent:

надсилає питання в UI,

чекає відповіді користувача,

підклеює її в контекст і запускає наступний крок.

Result delivery

якщо агент записав файл: повертає користувачу коротке пояснення + “де лежить файл” + (опційно) що робити далі.

2.2. Веб-сторінка

Ендпоінти:

POST /chat/send (text + attachments refs)

GET /chat/poll або WS для стріму відповідей

UI має вміти показати:

звичайну відповідь

питання (зручний form)

результат у файл (кнопка “download/open” якщо є)

Acceptance criteria:

Будь-яке завдання проходить через ChatAgent; середні агенти не спілкуються напряму з UI.

3) Доступ до file-агентів для виконання задач
3.1. Окремі атомарні агенти (як у вас уже є)

file_list_agent — список файлів у дозволених директоріях

file_read_agent — читання (з лімітом розміру + allowlist path)

file_write_agent — запис (з політикою перезапису / версіонування)

(опційно) file_search_agent — grep/пошук по проекту

3.2. Правила доступу (щоб не ламати проект)

allowlist директорій: наприклад тільки project_root/ + project_root/data/ + project_root/output/

denylist: .git/, venv/, node_modules/, secrets

ліміти: max size read/write

лог: хто/коли/що читав/писав

Acceptance criteria:

Оркестратор може зробити “подивись проект” через file_list + file_read, а не “з голови”.

4) Python/Shell агент (опційно, але ти просиш — робимо)
4.1. Атомарний агент python_exec_agent

Приймає:

cwd (за замовчуванням project_root)

code (строка)

timeout_sec

capture_stdout/stderr

Повертає:

stdout, stderr, exit_status

(опційно) створені файли (список)

4.2. Атомарний агент shell_exec_agent

Приймає:

command як масив токенів (без shell injection через одну строку)

cwd, timeout

Політика безпеки:

allowlist команд (на старті): ls, cat, python, pytest, git status (опційно), ripgrep

заборонити: мережеві команди, rm -rf, будь-які destructive без окремого режиму dev

Повний лог команд.

Acceptance criteria:

Система може запускати тести/скрипти, але не може “випадково” знести проект.

5) Перепрошивка логіки планування (щоб executor не “імітував виконання”)

Тут конкретні правки по ваших YAML/промптах (без зміни концепції агентів):

5.1. task_classifier — додаємо критерій “виконуваність”

Якщо завдання вимагає файлів/інструментів/доступу до проекту:

не може бути simple_answer

класифікувати як complex або needs_tools

5.2. llm_simple_answer — заборона галюцинацій

Додати правило: якщо недостатньо даних — status=blocked і список missing_inputs.

5.3. plan_executor — перетворити на “контролер”

Заборонити “виконав крок” без реального tool-call.

Кожен пункт плану має:

або виклик підлеглого агента (file_read, python_exec, …)

або перейти в blocked і задати питання користувачу через ChatAgent.

5.4. llm_summary — не вигадувати деталі

Саммарі має брати факти лише з execution_result / logs / tool outputs.

Acceptance criteria:

Якщо інструментів нема або даних нема — система не дає “відповідь з повітря”, а задає питання.

6) Механіка “результат у файл” як норма
6.1. Стандартний вихідний контракт для будь-якої задачі

Агент може повернути:

final_message_to_user (коротко)

artifacts:

{ type: "file", path: "...", description: "..."}

next_questions (якщо потрібно)

6.2. ChatAgent поведінка

Якщо є artifacts.file:

показує користувачу: “Зроблено. Результат збережено в …”

додає кнопки/посилання (якщо UI підтримує)

Acceptance criteria:

Складні звіти/витяги з мануалів/списки деталей — пишуться у файл, а не в чат полотном.

7) Тест-план (щоб це не зламалося потім)
7.1. Юніт-тести (мінімум)

task_classifier не відправляє file-dependent таски в simple

plan_executor не може видати ok без жодного tool output

file_* агенти: allow/deny path, ліміти розміру

7.2. Інтеграційні сценарії (обов’язково)

“Подивись структуру проекту і поясни логіку”
→ має бути file_list + file_read, а не вигадка

“Згенеруй звіт і запиши у файл”
→ file_write, в чаті лише пояснення

“Потрібні уточнення”
→ executor повертає blocked → ChatAgent питає → продовжує

8) Розклад робіт (по етапах)
Етап 1 (фундамент)

Протокол AgentEnvelope + статуси ok/blocked/error

ChatAgent (мінімальна версія: receive → forward → reply)

Інтеграція з UI (send/poll або websocket)

Етап 2 (інструменти як агенти)

file_list/read/write агенти з політиками доступу

прокидування tooling_state у всі промпти

Етап 3 (анти-галюцинації)

правки classifier/simple/executor/summary як описано вище

інтеграційні тести на “blocked” цикл

Етап 4 (опційно: python/shell)

python_exec_agent + shell_exec_agent з allowlist

тест “запустити тести проекту та зберегти лог у файл”
