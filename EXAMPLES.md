# Примеры использования

## Пример 1: Обработка Issue через CLI

```bash
# Обработать Issue полностью (Code Agent + Reviewer + итерации)
coding-agents process-issue --repo owner/repo-name --issue 42

# С указанием начальной итерации
coding-agents process-issue --repo owner/repo-name --issue 42 --iteration 2
```

## Пример 2: Только Code Agent

```bash
# Создать PR для Issue
coding-agents code-agent --repo owner/repo-name --issue 42

# Обновить существующий PR
coding-agents code-agent --repo owner/repo-name --issue 42 --pr 123 --iteration 2

# С указанием ветки
coding-agents code-agent --repo owner/repo-name --issue 42 --branch feature/new-feature
```

## Пример 3: Только Reviewer

```bash
# Проверить PR и опубликовать review
coding-agents reviewer --repo owner/repo-name --pr 123

# Без ожидания CI
coding-agents reviewer --repo owner/repo-name --pr 123 --no-wait-ci
```

## Пример 4: Использование API

```bash
# Запуск сервера
uvicorn coding_agents.api.server:app --host 0.0.0.0 --port 8000

# Обработка Issue
curl -X POST http://localhost:8000/api/process-issue \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "owner/repo-name",
    "issue_number": 42,
    "start_iteration": 1
  }'

# Запуск Code Agent
curl -X POST http://localhost:8000/api/code-agent \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "owner/repo-name",
    "issue_number": 42,
    "iteration_number": 1
  }'

# Запуск Reviewer
curl -X POST http://localhost:8000/api/reviewer \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "owner/repo-name",
    "pr_number": 123,
    "wait_for_ci": true
  }'
```

## Пример 5: GitHub Actions

Добавьте workflow в `.github/workflows/code_agent_workflow.yml`:

```yaml
name: Code Agent

on:
  issues:
    types: [opened]

jobs:
  code-agent:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -e .
      - run: |
          coding-agents process-issue \
            --repo "${{ github.repository }}" \
            --issue ${{ github.event.issue.number }}
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

## Пример 6: Docker

```bash
# Создать .env файл
cat > .env << EOF
GITHUB_TOKEN=your_token
OPENAI_API_KEY=your_key
LLM_PROVIDER=openai
MAX_ITERATIONS=5
EOF

# Запустить
docker-compose up -d

# Проверить логи
docker-compose logs -f

# Остановить
docker-compose down
```

## Пример 7: Webhook (GitHub App)

1. Создайте GitHub App с webhook URL: `https://your-domain.com/webhook/github`
2. Укажите `WEBHOOK_SECRET` в настройках App и в `.env`
3. Подпишитесь на события: `issues`, `pull_request`, `check_suite`

Система автоматически будет обрабатывать:
- Новые Issues → запуск Code Agent
- Новые/обновлённые PR → запуск Reviewer
- Завершение CI → опционально запуск Reviewer

## Пример Issue для тестирования

Создайте Issue с таким содержимым:

```markdown
## Задача

Добавить функцию для вычисления факториала числа.

## Требования

1. Функция должна принимать целое число n
2. Возвращать факториал n (n!)
3. Обрабатывать случай n=0 (возвращать 1)
4. Добавить unit-тесты

## Файлы для изменения

- `src/math_utils.py` - добавить функцию `factorial(n)`
- `tests/test_math_utils.py` - добавить тесты
```

Система автоматически:
1. Проанализирует Issue
2. Создаст код
3. Создаст PR
4. Запустит Reviewer
5. При необходимости исправит код и повторит цикл
