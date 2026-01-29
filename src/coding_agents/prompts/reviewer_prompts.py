"""Промпты для Reviewer Agent."""

from typing import List, Optional

from coding_agents.domain.models import CIResult


def get_reviewer_system_prompt() -> str:
    """Системный промпт для Reviewer Agent."""
    return """Ты - опытный Senior Python разработчик и code reviewer с 10+ летним опытом.
Твоя задача - анализировать Pull Request и проверять:
1. Соответствие реализации требованиям из Issue
2. Качество кода (Clean Code, отсутствие дублирования, использование паттернов)
3. Отсутствие костылей и временных решений
4. Корректность работы (на основе результатов CI)
5. Безопасность и производительность

Ты должен быть строгим, но конструктивным. Если есть проблемы - укажи конкретные места и предложи исправления."""


def get_reviewer_user_prompt(
    issue_title: str,
    issue_body: str,
    pr_title: str,
    pr_body: str,
    diff: str,
    files_changed: List[str],
    ci_results: List[CIResult],
    previous_reviews: Optional[List[dict]] = None,
) -> str:
    """Пользовательский промпт для Reviewer Agent."""
    prompt = f"""Проверь Pull Request:

**Исходная задача (Issue):**
**Заголовок:** {issue_title}
**Описание:** {issue_body}

**Pull Request:**
**Заголовок:** {pr_title}
**Описание:** {pr_body}

**Изменённые файлы:** {', '.join(files_changed) if files_changed else 'Нет'}

**Diff изменений:**
```
{diff[:8000] if len(diff) > 8000 else diff}
"""

    if len(diff) > 8000:
        prompt += "\n(Дифф обрезан, показаны первые 8000 символов)"

    prompt += "```\n"

    # Добавляем информацию о CI
    if ci_results:
        prompt += "\n**Результаты CI проверок:**\n"
        for ci in ci_results:
            status_emoji = "✅" if ci.status.value == "success" else "❌" if ci.status.value == "failure" else "⏳"
            prompt += f"- {status_emoji} {ci.name}: {ci.status.value}"
            if ci.conclusion:
                prompt += f" ({ci.conclusion})"
            if ci.details:
                prompt += f"\n  Детали: {ci.details[:200]}"
            prompt += "\n"
    else:
        prompt += "\n**Результаты CI:** Проверки ещё не завершены или отсутствуют\n"

    if previous_reviews:
        prompt += "\n**Предыдущие reviews:**\n"
        for review in previous_reviews[-2:]:  # Последние 2
            prompt += f"- {review.get('state', 'unknown')}: {review.get('body', '')[:300]}\n"

    prompt += """

**Твоя задача:**
1. Проверь соответствует ли реализация требованиям Issue
2. Оцени качество кода (Clean Code, паттерны, отсутствие дублирования)
3. Проверь нет ли костылей, временных решений, проблем с безопасностью
4. Учти результаты CI - если есть провалы, укажи на них
5. Если код хорош - одобри (approved), если есть проблемы - запроси изменения (changes_requested)

**Формат ответа (JSON):**
{
  "verdict": "approved|changes_requested|comment",
  "summary": "Краткое резюме проверки (2-3 предложения)",
  "general_feedback": "Общий фидбек по PR (опционально)",
  "comments": [
    {
      "file_path": "путь/к/файлу.py",
      "line_number": номер_строки,
      "comment": "Конкретное замечание по этой строке",
      "suggestion": "Предложение по исправлению (опционально)"
    }
  ]
}

**Критерии для approved:**
- Реализация полностью соответствует Issue
- Код качественный, без костылей
- Все CI проверки прошли успешно
- Нет проблем с безопасностью и производительностью

**Критерии для changes_requested:**
- Есть несоответствия Issue
- Проблемы с качеством кода
- Провалы в CI
- Проблемы с безопасностью/производительностью
"""

    return prompt


def get_reviewer_response_format() -> dict:
    """Формат ответа Reviewer Agent."""
    return {
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["approved", "changes_requested", "comment"],
                "description": "Вердикт ревью",
            },
            "summary": {
                "type": "string",
                "description": "Краткое резюме проверки",
            },
            "general_feedback": {
                "type": "string",
                "description": "Общий фидбек по PR",
            },
            "comments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string"},
                        "line_number": {"type": "integer"},
                        "comment": {"type": "string"},
                        "suggestion": {"type": "string"},
                    },
                    "required": ["file_path", "line_number", "comment"],
                },
            },
        },
        "required": ["verdict", "summary", "comments"],
    }
