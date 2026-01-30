"""Сервис Code Agent для генерации и применения изменений кода."""

import logging
import os
import time
from pathlib import Path
from typing import List, Optional

from coding_agents.config import settings
from coding_agents.domain.interfaces import GitHubClientInterface, GitOperationsInterface, LLMClientInterface
from coding_agents.domain.models import AgentExecutionResult, CodeAgentContext, CodeChange
from coding_agents.infrastructure.git_operations import GitOperations
from coding_agents.prompts.code_agent_prompts import (
    get_code_agent_response_format,
    get_code_agent_system_prompt,
    get_code_agent_user_prompt,
)

logger = logging.getLogger(__name__)


class CodeAgentService:
    """Сервис для автоматической генерации кода."""

    def __init__(
        self,
        github_client: GitHubClientInterface,
        llm_client: LLMClientInterface,
        git_operations: Optional[GitOperationsInterface] = None,
    ):
        """Инициализация сервиса."""
        self.github_client = github_client
        self.llm_client = llm_client
        self.git_operations = git_operations or GitOperations()

    def execute(self, context: CodeAgentContext, timeout: int = 300) -> AgentExecutionResult:
        """Выполнить задачу по генерации кода."""
        start_time = time.time()
        repo = context.repository
        issue_number = context.issue_number
        pr_number = context.pr_number
        iteration_number = context.iteration_number
        previous_feedback = context.previous_feedback
        branch = context.branch

        try:
            # Получаем данные о задаче
            logger.info(f"Получение Issue #{issue_number} из {repo}")
            issue = self.github_client.get_issue(repo, issue_number)

            # Формируем ветку если не указана
            if not branch:
                branch = f"issue-{issue_number}-iter-{iteration_number}"

            # 1. ГЛУБОКИЙ АНАЛИЗ КОНТЕКСТА
            # Сначала получаем структуру, чтобы понять где искать код
            repo_structure = self._get_repository_structure(repo)
            
            # 2. АНАЛИЗ СУЩЕСТВУЮЩЕГО КОДА ДЛЯ КОНКРЕТНОЙ ЗАДАЧИ
            # Мы просим LLM сначала сказать, какие файлы ей нужно прочитать
            # Но для упрощения в текущей версии мы сами попробуем найти релевантные файлы
            relevant_files_context = self._get_relevant_files_content(repo, issue.title + " " + issue.body)
            
            full_context = f"{repo_structure}\n\n{relevant_files_context}"

            # Формируем промпт
            system_prompt = get_code_agent_system_prompt()
            user_prompt = get_code_agent_user_prompt(
                issue_title=issue.title,
                issue_body=issue.body,
                repository_structure=full_context,
                previous_feedback=previous_feedback,
                iteration_number=iteration_number,
            )

            # Проверяем таймаут
            if time.time() - start_time > timeout:
                return AgentExecutionResult(
                    success=False,
                    message=f"Превышен таймаут {timeout} секунд",
                )

            # Вызываем LLM
            logger.info(f"Генерация кода для Issue #{issue_number}")
            response_format = get_code_agent_response_format()
            llm_response = self.llm_client.generate_structured(
                prompt=user_prompt,
                system_prompt=system_prompt,
                response_format=response_format,
            )

            # Парсим ответ
            plan = llm_response.get("plan", "")
            changes_data = llm_response.get("changes", [])
            commit_message = llm_response.get("commit_message", f"Fix: {issue.title}")

            # Преобразуем в CodeChange
            changes = []
            for change_data in changes_data:
                try:
                    # Валидация: предотвращаем пустой контент
                    content = change_data.get("content", "")
                    if change_data["operation"] in ["create", "modify"] and (not content or len(content.strip()) < 10):
                        logger.warning(f"Пропущено подозрительно короткое изменение для {change_data['file_path']}")
                        # Если это единственный файл, то это ошибка
                        if len(changes_data) == 1:
                            raise ValueError(f"LLM предложил пустое или слишком короткое решение для {change_data['file_path']}")
                        continue

                    change = CodeChange(
                        file_path=change_data["file_path"],
                        operation=change_data["operation"],
                        content=content,
                        old_content=change_data.get("old_content"),
                        line_start=change_data.get("line_start"),
                        line_end=change_data.get("line_end"),
                    )
                    changes.append(change)
                except (KeyError, ValueError) as e:
                    logger.warning(f"Ошибка в данных изменения: {e}")
                    continue

            if not changes:
                return AgentExecutionResult(
                    success=False,
                    message="LLM не вернул валидных изменений кода. Пожалуйста, уточните задачу.",
                )

            logger.info(f"Получено {len(changes)} изменений от LLM")

            # Применяем изменения к репозиторию
            repo_local_path = self._prepare_repository(repo, branch)

            logger.info(f"Применение изменений к репозиторию {repo_local_path}")
            self.git_operations.apply_changes(repo_local_path, changes)

            # Коммитим
            logger.info("Создание коммита")
            commit_sha = self.git_operations.commit_changes(
                repo_local_path,
                commit_message,
                author_name="Code Agent",
                author_email="code-agent@github.com",
            )

            # Пушим
            logger.info(f"Push изменений в ветку {branch}")
            token = settings.get_github_token()
            self.git_operations.push_changes(repo_local_path, branch, token=token)

            # Создаём или обновляем PR
            if not pr_number:
                logger.info(f"Поиск существующего PR для ветки {branch}")
                existing_pr = self.github_client.get_pr_by_branch(repo, branch)
                if existing_pr:
                    pr_number = existing_pr.number
                    logger.info(f"Найден существующий PR #{pr_number}")

            if pr_number:
                logger.info(f"Обновление PR #{pr_number}")
                self.github_client.update_pr(repo, pr_number, body=f"**План:** {plan}\n\n**Итерация:** {iteration_number}")
            else:
                logger.info("Создание нового PR")
                base_branch = self.git_operations.get_default_branch(repo_local_path)
                pr_number = self.github_client.create_pr(
                    repo=repo,
                    title=f"{issue.title} (Iteration {iteration_number})",
                    body=f"**План:** {plan}\n\n**Связано с Issue:** #{issue_number}",
                    head=branch,
                    base=base_branch,
                )

            logger.info(f"Code Agent успешно выполнен. PR #{pr_number}")

            return AgentExecutionResult(
                success=True,
                message=f"Изменения применены, создан/обновлён PR #{pr_number}",
                pr_number=pr_number,
                branch=branch,
                changes=changes,
            )

        except Exception as e:
            logger.error(f"Ошибка выполнения Code Agent: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return AgentExecutionResult(
                success=False,
                message=f"Ошибка: {str(e)}",
            )

    def _prepare_repository(self, repo: str, branch: str) -> str:
        """Подготовить локальный репозиторий."""
        repo_name = repo.split("/")[-1]
        repo_local_path = os.path.join(settings.work_dir, repo_name)
        
        git_ops = self.git_operations
        token = settings.get_github_token()
        
        # Клонируем если нет
        if not os.path.exists(repo_local_path):
            logger.info(f"Клонирование репозитория {repo}")
            repo_url = f"https://github.com/{repo}.git"
            git_ops.clone_repository(repo_url, repo_local_path, token=token)
        
        # Переключаемся на ветку
        try:
            logger.info(f"Переключение на ветку {branch}")
            git_ops.checkout_branch(repo_local_path, branch, create=True)
        except Exception as e:
            logger.debug(f"Ветка {branch} уже существует или ошибка: {e}")
            try:
                git_ops.checkout_branch(repo_local_path, branch, create=False)
            except Exception:
                git_ops.checkout_branch(repo_local_path, branch, create=True)

        return repo_local_path

    def _get_repository_structure(self, repo: str) -> str:
        """Получить структуру репозитория и важные файлы."""
        try:
            logger.info(f"Получение структуры репозитория {repo}")
            tree = self.github_client.get_repository_tree(repo, max_depth=3)
            if not tree:
                return "Структура репозитория недоступна."
            
            context_parts = ["## СТРУКТУРА ПРОЕКТА", tree, ""]
            
            # Конфигурационные файлы
            config_files = ["pyproject.toml", "requirements.txt", "package.json", "setup.py", "README.md"]
            for file_path in config_files:
                content = self.github_client.get_file_content(repo, file_path)
                if content:
                    context_parts.append(f"### Файл: {file_path}\n```\n{content[:2000]}\n```")
            
            return "\n".join(context_parts)
        except Exception as e:
            logger.warning(f"Ошибка при получении структуры: {e}")
            return "Ошибка при получении структуры проекта."

    def _get_relevant_files_content(self, repo: str, query: str) -> str:
        """Найти и прочитать файлы, релевантные задаче."""
        try:
            context_parts = ["## СУЩЕСТВУЮЩИЙ КОД ДЛЯ АНАЛИЗА"]
            
            # 1. Находим все файлы (плоский список)
            all_files = self._get_all_files_recursive(repo)
            
            # 2. Простая эвристика поиска релевантных файлов по ключевым словам из задачи
            keywords = query.lower().split()
            relevant_paths = []
            
            for path in all_files:
                path_lower = path.lower()
                # Игнорируем тесты при поиске исходников (если только задача не про тесты)
                if "test" in query.lower() or "тест" in query.lower():
                    pass # Если ищем тесты, то не игнорируем
                elif "test" in path_lower:
                    continue
                    
                if any(kw in path_lower for kw in keywords if len(kw) > 3):
                    relevant_paths.append(path)
            
            # 3. Если ничего не нашли, берем "главные" файлы
            if not relevant_paths:
                main_candidates = ["main.py", "app.py", "src/main.py", "src/app.py", "api/server.py"]
                relevant_paths = [p for p in main_candidates if p in all_files]

            # 4. Читаем содержимое (макс 5 файлов)
            for path in relevant_paths[:7]:
                content = self.github_client.get_file_content(repo, path)
                if content:
                    context_parts.append(f"### Файл: {path}\n```python\n{content[:4000]}\n```")
            
            if len(context_parts) == 1:
                return "Релевантный код не найден. Пожалуйста, создай новые файлы согласно архитектуре."
                
            return "\n".join(context_parts)
        except Exception as e:
            logger.warning(f"Ошибка при поиске релевантных файлов: {e}")
            return ""

    def _get_all_files_recursive(self, repo: str, path: str = "", depth: int = 0) -> List[str]:
        """Рекурсивно получить список всех файлов."""
        if depth > 3: return []
        files = []
        try:
            items = self.github_client.get_repository_files(repo, path)
            for item in items:
                if item["type"] == "dir":
                    if item["path"].split("/")[-1] not in [".git", "__pycache__", "venv", "node_modules"]:
                        files.extend(self._get_all_files_recursive(repo, item["path"], depth + 1))
                else:
                    files.append(item["path"])
        except Exception:
            pass
        return files
