# LangChain + Ollama + Neo4j knowledge graph tool

Цей приклад демонструє утиліту, яка приймає текстовий вхід, генерує граф знань за допомогою LangChain і локальної LLM в Ollama, а потім зберігає граф у Neo4j. Додатково можна ввімкнути періодичну перевірку графа, що шукає помилки та пропонує нові зв'язки.

## Встановлення
1. Встановіть залежності:
   ```bash
   pip install -r requirements.txt
   ```
2. Переконайтесь, що в Ollama доступна потрібна модель (за замовчуванням `llama3`).
3. Запустіть Neo4j (наприклад, у Docker) і налаштуйте доступ за допомогою змінних середовища:
   ```bash
   export NEO4J_URL=bolt://localhost:7687
   export NEO4J_USERNAME=neo4j
   export NEO4J_PASSWORD=your_password
   # Необов'язково:
   export NEO4J_DATABASE=neo4j
   export OLLAMA_MODEL=llama3
   export VERIFICATION_INTERVAL_SECONDS=900
   export MAX_RELATIONSHIP_SUGGESTIONS=5
   ```

## Використання
Інжест тексту з файлу та запуск верифікатора у фоні:
```bash
python -m graph_tool.cli --input-file ./data/article.txt --start-verifier --interval 600
```

Інжест короткого фрагменту тексту без довготривалого процесу:
```bash
python -m graph_tool.cli --text "Шевченко Тарас Григорович — український поет." 
```

### Що відбувається
- `KnowledgeGraphBuilder` нарізає довгий текст на вікна (з перекриттям), передає кожен шматок у `LLMGraphTransformer`, витягує сутності/зв'язки та **мерджить** вузли/ребра в Neo4j через `MERGE`, щоб уникати дублікатів.
- `GraphVerifier` за розкладом виконує кілька перевірок: знаходить сирітські вузли, дублікати і за допомогою LLM пропонує потенційні зв'язки між вузлами, після чого зберігає їх у графі.

## Архітектура коду
- `src/graph_tool/config.py` — налаштування підключення та параметри LLM/верифікації.
- `src/graph_tool/builder.py` — побудова графа з тексту через LangChain та Ollama.
- `src/graph_tool/verifier.py` — фонові перевірки та збагачення графа.
- `src/graph_tool/cli.py` — CLI для інжесту тексту та запуску верифікації.
