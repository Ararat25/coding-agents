# Changelog

## [0.1.0] - 2026-01-29

### Added
- Code Agent - генерация кода на основе GitHub Issue
- AI Reviewer Agent - автоматический анализ Pull Request
- SDLC Orchestrator - полный цикл разработки с итерациями
- CLI интерфейс для запуска агентов
- REST API для интеграции
- Webhook endpoint для GitHub событий
- GitHub Actions workflows
- Docker поддержка
- Поддержка OpenAI и YandexGPT
- Защита от бесконечных циклов (лимит итераций)
- Автоматическое ожидание завершения CI

### Features
- Автоматическое создание и обновление Pull Request
- Анализ соответствия кода требованиям Issue
- Проверка качества кода (Clean Code принципы)
- Учёт результатов CI при review
- Итеративная разработка до получения approved review
- Поддержка нескольких LLM провайдеров

### Documentation
- Полная документация в README.md
- Примеры использования в EXAMPLES.md
- Быстрый старт в QUICKSTART.md
- Детальный план реализации в docs/
