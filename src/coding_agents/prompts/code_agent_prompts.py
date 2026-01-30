"""Промпты для Code Agent."""

from typing import Optional


def get_code_agent_system_prompt() -> str:
    """Системный промпт для Code Agent."""
    return """Ты - опытный Senior Python разработчик с 10+ летним опытом.
Твоя задача - анализировать требования из GitHub Issue и реализовывать их в коде.

Принципы работы:
1. Следуй принципам Clean Code: читаемость, отсутствие дублирования, использование паттернов где уместно
2. Не создавай костыли и временные решения
3. Пиши качественный, поддерживаемый код
4. Если в репозитории есть тесты - не ломай их, при необходимости добавь новые
5. Следуй стилю кода существующего проекта
6. Если есть замечания от Reviewer - учти их при исправлениях
7. ВНИМАТЕЛЬНО ИЗУЧИ структуру проекта, документацию и существующий код
8. Реализуй КОНКРЕТНОЕ решение, а не общие формулировки
9. Используй контекст проекта для интеграции с существующим кодом

Ты должен вернуть структурированный JSON с планом изменений и самими изменениями."""


def get_code_agent_user_prompt(
    issue_title: str,
    issue_body: str,
    repository_structure: Optional[str] = None,
    previous_feedback: Optional[str] = None,
    iteration_number: int = 1,
) -> str:
    """Пользовательский промпт для Code Agent."""
    prompt = f"""Задача из GitHub Issue:

**Заголовок:** {issue_title}

**Описание:**
{issue_body}
"""

    if previous_feedback:
        prompt += f"""

**Замечания от Reviewer (итерация {iteration_number - 1}):**
{previous_feedback}

Учти эти замечания при исправлении кода.
"""

    if repository_structure:
        prompt += f"""

**КОНТЕКСТ ПРОЕКТА (ОБЯЗАТЕЛЬНО ИЗУЧИ!):**
{repository_structure}

ВАЖНО: Используй этот контекст для:
- Понимания архитектуры проекта
- Соблюдения стиля кода и паттернов
- Интеграции с существующими классами и функциями
- Использования правильных импортов и зависимостей
"""
    else:
        prompt += """

ПРЕДУПРЕЖДЕНИЕ: Контекст проекта недоступен. Реализуй решение на основе общепринятых практик Python.
"""

    prompt += """

**Твоя задача:**
1. Проанализируй требования
2. Определи какие файлы нужно создать/изменить/удалить
3. Реализуй изменения в коде

**Формат ответа (JSON):**
{
  "plan": "Краткое описание плана реализации",
  "changes": [
    {
      "file_path": "путь/к/файлу.py",
      "operation": "create|modify|delete",
      "content": "полное содержимое файла (для create/modify)",
      "old_content": "старое содержимое (только для modify, если нужно точечное изменение)",
      "line_start": номер_строки_начала (опционально, для точечного изменения),
      "line_end": номер_строки_конца (опционально, для точечного изменения)
    }
  ],
  "commit_message": "Краткое описание изменений для коммита"
}

**Важно:**
- Для operation="modify" можно указать либо полный content (замена всего файла), либо old_content + line_start/line_end (точечное изменение)
- Все пути файлов должны быть относительными от корня репозитория
- Код должен быть рабочим и следовать стилю проекта
- Если нужно добавить зависимости - укажи это в plan, но не меняй файлы зависимостей без необходимости
"""

    return prompt


def get_code_agent_response_format() -> dict:
    """Формат ответа Code Agent."""
    return {
        "type": "object",
        "properties": {
            "plan": {
                "type": "string",
                "description": "Краткое описание плана реализации",
            },
            "changes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string"},
                        "operation": {"type": "string", "enum": ["create", "modify", "delete"]},
                        "content": {"type": "string"},
                        "old_content": {"type": "string"},
                        "line_start": {"type": "integer"},
                        "line_end": {"type": "integer"},
                    },
                    "required": ["file_path", "operation"],
                },
            },
            "commit_message": {"type": "string"},
        },
        "required": ["plan", "changes", "commit_message"],
    }
