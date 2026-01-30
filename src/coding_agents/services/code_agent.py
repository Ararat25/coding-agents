"""Code Agent - сервис для генерации кода на основе Issue."""

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
    """Сервис Code Agent."""

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

    def execute(
        self,
        repo: str,
        issue_number: int,
        branch: Optional[str] = None,
        pr_number: Optional[int] = None,
        previous_feedback: Optional[str] = None,
        iteration_number: int = 1,
    ) -> AgentExecutionResult:
        """Выполнить задачу Code Agent."""
        start_time = time.time()
        timeout = settings.code_agent_timeout

        try:
            # Получаем Issue
            logger.info(f"Получение Issue #{issue_number} из {repo}")
            issue = self.github_client.get_issue(repo, issue_number)

            # Формируем ветку если не указана
            if not branch:
                branch = f"issue-{issue_number}-iter-{iteration_number}"

            # Получаем структуру репозитория (опционально)
            repo_structure = self._get_repository_structure(repo)

            # Формируем промпт
            system_prompt = get_code_agent_system_prompt()
            user_prompt = get_code_agent_user_prompt(
                issue_title=issue.title,
                issue_body=issue.body,
                repository_structure=repo_structure,
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
                    change = CodeChange(
                        file_path=change_data["file_path"],
                        operation=change_data["operation"],
                        content=change_data.get("content"),
                        old_content=change_data.get("old_content"),
                        line_start=change_data.get("line_start"),
                        line_end=change_data.get("line_end"),
                    )
                    changes.append(change)
                except KeyError as e:
                    logger.warning(f"Пропущено некорректное изменение: {e}")
                    continue

            if not changes:
                return AgentExecutionResult(
                    success=False,
                    message="LLM не вернул изменений для применения",
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
                # Пытаемся найти существующий PR для этой ветки
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
            logger.error(f"Ошибка выполнения Code Agent: {e}", exc_info=True)
            return AgentExecutionResult(
                success=False,
                message=f"Ошибка: {str(e)}",
            )

    def _prepare_repository(self, repo: str, branch: str) -> str:
        """Подготовить локальный клон репозитория."""
        from pathlib import Path

        # Формируем путь для локального клона
        repo_name = repo.replace("/", "_")
        repo_local_path = f"{repo_name}"

        repo_url = f"https://github.com/{repo}.git"
        token = settings.get_github_token()

        # Проверяем существует ли уже клон
        git_ops = self.git_operations
        base_path = Path(git_ops.base_repos_dir) / repo_local_path

        if not base_path.exists():
            # Клонируем
            logger.info(f"Клонирование репозитория {repo} в {repo_local_path}")
            git_ops.clone_repository(repo_url, repo_local_path, token)

        # Переключаемся на нужную ветку или создаём новую
        try:
            git_ops.checkout_branch(repo_local_path, branch, create=True)
        except Exception as e:
            logger.debug(f"Ветка {branch} уже существует или ошибка: {e}")
            # Ветка уже существует, переключаемся
            try:
                git_ops.checkout_branch(repo_local_path, branch, create=False)
            except Exception:
                # Если не получилось, создаём заново
                git_ops.checkout_branch(repo_local_path, branch, create=True)

        return repo_local_path

    def _get_repository_structure(self, repo: str) -> Optional[str]:
        """Получить структуру репозитория и важные файлы."""
        try:
            logger.info(f"Получение структуры репозитория {repo}")
            
            # Получаем дерево файлов
            tree = self.github_client.get_repository_tree(repo, max_depth=3)
            
            if not tree:
                return None
            
            context_parts = ["## Структура репозитория", tree, ""]
            
            # Получаем содержимое важных файлов
            important_files = [
                "README.md",
                "CONTRIBUTING.md",
                "ARCHITECTURE.md",
                "pyproject.toml",
                "package.json",
                "requirements.txt",
                "setup.py",
                ".env.example",
            ]
            
            context_parts.append("## Важные файлы и документация")
            
            for file_path in important_files:
                content = self.github_client.get_file_content(repo, file_path)
                if content:
                    # Ограничиваем размер файла для контекста
                    if len(content) > 5000:
                        content = content[:5000] + "\n... (файл обрезан)"
                    context_parts.append(f"\n### {file_path}\n```\n{content}\n```")
            
            # Получаем содержимое ключевых Python файлов
            python_files = self._find_key_python_files(repo)
            if python_files:
                context_parts.append("\n## Ключевые файлы кода")
                for file_path in python_files[:10]:  # Ограничиваем 10 файлами
                    content = self.github_client.get_file_content(repo, file_path)
                    if content:
                        if len(content) > 3000:
                            content = content[:3000] + "\n... (файл обрезан)"
                        context_parts.append(f"\n### {file_path}\n```python\n{content}\n```")
            
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.warning(f"Ошибка при получении структуры репозитория: {e}")
            return None
    
    def _find_key_python_files(self, repo: str) -> List[str]:
        """Найти ключевые Python файлы в репозитории."""
        try:
            key_files = []
            
            # Проверяем типичные пути
            common_paths = [
                "main.py",
                "app.py",
                "__init__.py",
                "src/__init__.py",
                "src/main.py",
                "src/app.py",
                "api/server.py",
                "src/api/server.py",
            ]
            
            for path in common_paths:
                content = self.github_client.get_file_content(repo, path)
                if content:
                    key_files.append(path)
            
            return key_files
            
        except Exception as e:
            logger.debug(f"Ошибка при поиске Python файлов: {e}")
            return []
