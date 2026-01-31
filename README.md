# Coding Agents - SDLC Автоматизация

Автоматизированная агентная система для полного цикла разработки программного обеспечения (SDLC) внутри GitHub.

## Описание

Система состоит из двух агентов:

1. **Code Agent** - анализирует GitHub Issue, генерирует код и создаёт Pull Request
2. **AI Reviewer Agent** - анализирует Pull Request, проверяет соответствие Issue, качество кода и результаты CI, публикует review

Агенты работают итеративно: Code Agent создаёт код → Reviewer проверяет → при необходимости Code Agent исправляет → цикл повторяется до успеха или лимита итераций.

## Архитектура

```
┌─────────────┐
│ GitHub Issue│
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│  Code Agent     │ ──► Создаёт/обновляет PR
└─────────────────┘
       │
       ▼
┌─────────────────┐
│  CI/CD Pipeline │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│ Reviewer Agent  │ ──► Публикует review
└──────┬──────────┘
       │
       ├─► APPROVED ──► ✅ Готово
       │
       └─► CHANGES_REQUESTED ──► Code Agent (итерация)
```

## Сервис развернут в облаке и досупен по адресу
## http://158.160.160.54:80/api/process-issue

## Как быстро начать

**Подробная пошаговая инструкция:**

Кратко:
1. Создай `.env` в корне проекта с `GITHUB_TOKEN` и `OPENAI_API_KEY`.
2. Запусти: `docker-compose build --no-cache && docker-compose up -d`.
3. Вызови API: `POST http://localhost:8000/api/process-issue` с телом:
   ```json
   {"repo": "владелец/имя-репо", "issue_number": 42, "start_iteration": 1}
   ```
   Репозиторий и Issue с этим номером должны существовать в GitHub; токен должен иметь доступ к репо.

## Требования

- Python 3.11+
- GitHub токен или GitHub App
- API ключ для LLM (OpenAI или YandexGPT)

## Установка

### Локальная установка

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd coding-agents
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
pip install -e .
```

3. Настройте переменные окружения:
```bash
cp .env.example .env
# Отредактируйте .env и укажите ваши ключи
```

### Docker

1. Скопируйте `.env.example` в `.env` и настройте переменные

2. Запустите:
```bash
docker-compose up -d
```

Сервис будет доступен на `http://localhost:8000`

## Конфигурация

### Переменные окружения

См. `.env.example` для полного списка. Основные:

- `GITHUB_TOKEN` - токен GitHub (обязательно)
- `LLM_PROVIDER` - провайдер LLM: `openai` или `yandex` (по умолчанию: `openai`)
- `OPENAI_API_KEY` - ключ OpenAI (если используется OpenAI)
- `YANDEX_API_KEY` - ключ YandexGPT (если используется YandexGPT)
- `YANDEX_FOLDER_ID` - ID папки Yandex Cloud
- `OPENAI_BASE_URL` - альтернативный URL API (обход гео-ограничений)
- `HTTP_PROXY` / `HTTPS_PROXY` - прокси для исходящих запросов (обход гео)
- `MAX_ITERATIONS` - максимальное количество итераций (по умолчанию: 5)
- `WEBHOOK_SECRET` - секрет для проверки подписи webhook (опционально)
- `WEBHOOK_PORT` - порт для API/webhook (по умолчанию: 8000)

## Использование

### CLI

#### Обработка Issue полностью (Code Agent + Reviewer + итерации)

```bash
coding-agents process-issue --repo owner/repo --issue 123
```

#### Только Code Agent

```bash
coding-agents code-agent --repo owner/repo --issue 123 --branch issue-123
```

#### Только Reviewer Agent

```bash
coding-agents reviewer --repo owner/repo --pr 456
```

### API

#### Запуск API сервера

```bash
python -m coding_agents.api.server
# или
uvicorn coding_agents.api.server:app --host 0.0.0.0 --port 8000
```

#### Endpoints

- `GET /health` - проверка здоровья
- `POST /api/process-issue` - обработка Issue
- `POST /api/code-agent` - запуск Code Agent
- `POST /api/reviewer` - запуск Reviewer Agent
- `POST /webhook/github` - webhook для GitHub событий

Пример запроса:
```bash
curl -X POST http://localhost:8000/api/process-issue \
  -H "Content-Type: application/json" \
  -d '{"repo": "owner/repo", "issue_number": 123}'
```

### GitHub Actions

Скопируйте workflows из `.github/workflows/` в ваш репозиторий:

1. `code_agent_workflow.yml` - запускается при создании Issue
2. `reviewer_workflow.yml` - запускается при создании/обновлении PR

Настройте secrets в GitHub:
- `GITHUB_TOKEN` (автоматически доступен)
- `OPENAI_API_KEY` или `YANDEX_API_KEY`
- `YANDEX_FOLDER_ID` (если используется YandexGPT)
- `LLM_PROVIDER` (опционально, по умолчанию `openai`)

### Webhook (GitHub App)

Для использования webhook:

1. Создайте GitHub App с правами:
   - Contents: Read & Write
   - Pull requests: Read & Write
   - Issues: Read & Write
   - Metadata: Read

2. Настройте webhook URL: `https://your-domain.com/webhook/github`

3. Укажите `WEBHOOK_SECRET` в переменных окружения

4. Подпишитесь на события:
   - `issues` (opened)
   - `pull_request` (opened, synchronize)
   - `check_suite` (completed) - опционально

## Структура проекта

```
coding-agents/
├── src/
│   └── coding_agents/
│       ├── config.py              # Конфигурация
│       ├── domain/                 # Доменные модели и интерфейсы
│       │   ├── models.py
│       │   └── interfaces.py
│       ├── infrastructure/         # Инфраструктурные компоненты
│       │   ├── github_client.py
│       │   ├── llm_client.py
│       │   └── git_operations.py
│       ├── services/               # Сервисы агентов
│       │   ├── code_agent.py
│       │   └── reviewer_agent.py
│       ├── prompts/                # Промпты для LLM
│       │   ├── code_agent_prompts.py
│       │   └── reviewer_prompts.py
│       ├── orchestration/          # Оркестрация SDLC
│       │   └── sdlc_orchestrator.py
│       ├── cli/                    # CLI интерфейс
│       │   └── main.py
│       └── api/                    # API и webhook
│           └── server.py
├── .github/
│   └── workflows/                  # GitHub Actions workflows
├── docs/                           # Документация
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Принципы работы

### Code Agent

1. Читает Issue и анализирует требования
2. Генерирует план реализации с помощью LLM
3. Создаёт/изменяет файлы в локальном клоне репозитория
4. Коммитит и пушит изменения
5. Создаёт или обновляет Pull Request

### Reviewer Agent

1. Получает PR и связанный Issue
2. Собирает diff, список файлов, результаты CI
3. Анализирует с помощью LLM:
   - Соответствие Issue
   - Качество кода (Clean Code, паттерны)
   - Результаты CI
   - Безопасность и производительность
4. Публикует review в PR с вердиктом (APPROVED / CHANGES_REQUESTED / COMMENT)

### Итерации

- При `CHANGES_REQUESTED` запускается следующая итерация Code Agent
- Максимальное количество итераций настраивается через `MAX_ITERATIONS`
- При достижении лимита процесс останавливается с комментарием в Issue

## Ограничения и известные проблемы

- LLM может генерировать неполный или некорректный код - требуется проверка
- Большие diff могут быть обрезаны (лимит токенов)
- CI проверки должны быть настроены в целевом репозитории
- Система не выполняет merge и deploy - только создаёт готовый PR

## Разработка

### Установка для разработки

```bash
pip install -r requirements.txt
pip install -e ".[dev]"
```

### Запуск тестов

```bash
pytest
```

### Линтинг и форматирование

```bash
ruff check .
black .
mypy src/
```
