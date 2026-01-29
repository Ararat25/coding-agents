# Быстрый старт

## 1. Установка

```bash
# Клонируйте репозиторий
git clone <repository-url>
cd coding-agents

# Установите зависимости
pip install -r requirements.txt
pip install -e .
```

## 2. Настройка

Скопируйте `.env.example` в `.env` и заполните:

```bash
cp .env.example .env
```

Минимальные настройки:
```env
GITHUB_TOKEN=your_github_token
OPENAI_API_KEY=your_openai_key
LLM_PROVIDER=openai
```

## 3. Первый запуск

### Вариант A: CLI

```bash
coding-agents process-issue --repo owner/repo-name --issue 1
```

### Вариант B: Docker

```bash
docker-compose up -d
```

### Вариант C: API

```bash
# Запустите сервер
uvicorn coding_agents.api.server:app --host 0.0.0.0 --port 8000

# В другом терминале
curl -X POST http://localhost:8000/api/process-issue \
  -H "Content-Type: application/json" \
  -d '{"repo": "owner/repo-name", "issue_number": 1}'
```

## 4. Проверка работы

1. Создайте Issue в тестовом репозитории
2. Запустите команду обработки Issue
3. Дождитесь создания PR
4. Проверьте review от Reviewer Agent

## 5. GitHub Actions (опционально)

Скопируйте workflows из `.github/workflows/` в ваш репозиторий и настройте secrets.

## Что дальше?

- См. `README.md` для полной документации
- См. `EXAMPLES.md` для примеров использования
- См. `docs/ПЛАН_РЕАЛИЗАЦИИ_И_АНАЛИЗ.md` для архитектуры
