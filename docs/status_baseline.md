# Статус baseline

## Як запускали
- Тести: `pytest`.
- Демо: `python run.py demo` (викликає `llm_prompt_chain` через ExecutionEngine + Dummy LLM factory).
- UI/бекенд: `python run.py web --host 127.0.0.2 --port 8002` (для автоматичної перевірки піднято на `0.0.0.0:8002`, щоб зробити curl-запуск ззовні; інтерфейс залишився доступним на 127.0.0.2:8002).

## Прогнаний workflow через UI API
- Агент: `llm_prompt_chain` (ланцюжок `prompt_builder` -> `llm_ollama` -> `output_collector`).
- Вхідні змінні LLM: `ollama_host="http://dummy.local"`, `ollama_model="demo-model"`, `temperature=0.25`, `користувацький_запит="UI запуск"`.
- Результат (Dummy LLM): `LLM(demo-model)@http://dummy.local: Ти помічник Codex. Відповідай українською. Запит: UI запуск`, використана_модель=`demo-model`.
- Виклик виконувався через `POST /api/run/llm_prompt_chain` (ідентичний тому, що викликає модалка запуску в UI), бо браузерний тул не зміг під’єднатись до 8002 (ERR_CONNECTION_REFUSED при спробі зробити скріншот).

## Використані LLM-змінні
- Обов’язкові: `ollama_host` (адреса), `ollama_model` (модель), `temperature` (числовий параметр), `prompt` формується в `prompt_builder`.
- Дефолти зі спеку агента (`options.model="llama3"`, `options.temperature=0.2`, `parse_json=false`) використовуються лише як локальні значення; вони перекриваються, якщо у вхідних змінних передано актуальні host/model/temperature.
