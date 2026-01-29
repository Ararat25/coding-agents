"""Интерфейсы для абстракций."""

from abc import ABC, abstractmethod
from typing import List, Optional

from coding_agents.domain.models import (
    CIResult,
    CodeAgentContext,
    IssueContext,
    PRContext,
    ReviewerContext,
)


class GitHubClientInterface(ABC):
    """Интерфейс для работы с GitHub API."""

    @abstractmethod
    def get_issue(self, repo: str, issue_number: int) -> IssueContext:
        """Получить Issue по номеру."""
        pass

    @abstractmethod
    def get_pr(self, repo: str, pr_number: int) -> PRContext:
        """Получить Pull Request по номеру."""
        pass

    @abstractmethod
    def get_pr_by_branch(self, repo: str, branch: str) -> Optional[PRContext]:
        """Получить Pull Request по ветке."""
        pass

    @abstractmethod
    def get_ci_results(self, repo: str, sha: str) -> List[CIResult]:
        """Получить результаты CI для коммита."""
        pass

    @abstractmethod
    def create_pr(
        self,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str,
    ) -> int:
        """Создать Pull Request. Возвращает номер PR."""
        pass

    @abstractmethod
    def update_pr(self, repo: str, pr_number: int, body: Optional[str] = None) -> None:
        """Обновить Pull Request."""
        pass

    @abstractmethod
    def create_review(
        self,
        repo: str,
        pr_number: int,
        body: str,
        event: str,
        comments: Optional[List[dict]] = None,
    ) -> None:
        """Создать review для PR."""
        pass

    @abstractmethod
    def create_comment(self, repo: str, issue_number: int, body: str) -> None:
        """Создать комментарий в Issue."""
        pass

    @abstractmethod
    def create_pr_comment(self, repo: str, pr_number: int, body: str) -> None:
        """Создать комментарий в PR."""
        pass

    @abstractmethod
    def get_pr_reviews(self, repo: str, pr_number: int) -> List[dict]:
        """Получить список reviews для PR."""
        pass


class LLMClientInterface(ABC):
    """Интерфейс для работы с LLM."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
    ) -> str:
        """Сгенерировать ответ от LLM."""
        pass

    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_format: Optional[dict] = None,
    ) -> dict:
        """Сгенерировать структурированный ответ (JSON)."""
        pass


class GitOperationsInterface(ABC):
    """Интерфейс для работы с Git."""

    @abstractmethod
    def clone_repository(self, repo_url: str, local_path: str, token: str) -> None:
        """Клонировать репозиторий."""
        pass

    @abstractmethod
    def checkout_branch(self, repo_path: str, branch: str, create: bool = False) -> None:
        """Переключиться на ветку."""
        pass

    @abstractmethod
    def apply_changes(
        self,
        repo_path: str,
        changes: List,
    ) -> None:
        """Применить изменения к репозиторию."""
        pass

    @abstractmethod
    def commit_changes(
        self,
        repo_path: str,
        message: str,
        author_name: str = "Code Agent",
        author_email: str = "code-agent@example.com",
    ) -> str:
        """Закоммитить изменения. Возвращает SHA коммита."""
        pass

    @abstractmethod
    def push_changes(
        self,
        repo_path: str,
        branch: str,
        remote: str = "origin",
        token: str = None,
    ) -> None:
        """Запушить изменения."""
        pass

    @abstractmethod
    def get_default_branch(self, repo_path: str) -> str:
        """Получить дефолтную ветку репозитория."""
        pass
