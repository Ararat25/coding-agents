"""Доменные модели данных."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional


class ReviewVerdict(str, Enum):
    """Вердикт ревьюера."""

    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    COMMENT = "comment"


class CIStatus(str, Enum):
    """Статус CI проверки."""

    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"
    PENDING = "pending"
    CANCELLED = "cancelled"


@dataclass
class CIResult:
    """Результат CI проверки."""

    name: str
    status: CIStatus
    conclusion: Optional[str] = None
    url: Optional[str] = None
    details: Optional[str] = None


@dataclass
class CodeChange:
    """Изменение в коде."""

    file_path: str
    operation: str  # "create", "modify", "delete"
    content: Optional[str] = None
    old_content: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None


@dataclass
class ReviewComment:
    """Комментарий ревьюера."""

    file_path: str
    line_number: int
    comment: str
    suggestion: Optional[str] = None


@dataclass
class ReviewResult:
    """Результат ревью."""

    verdict: ReviewVerdict
    summary: str
    comments: List[ReviewComment]
    general_feedback: Optional[str] = None


@dataclass
class IssueContext:
    """Контекст Issue."""

    number: int
    title: str
    body: str
    labels: List[str]
    state: str
    created_at: datetime
    updated_at: datetime


@dataclass
class PRContext:
    """Контекст Pull Request."""

    number: int
    title: str
    body: str
    head_branch: str
    base_branch: str
    head_sha: str
    state: str
    diff: str
    files_changed: List[str]
    created_at: datetime
    updated_at: datetime


@dataclass
class ReviewerContext:
    """Контекст для Reviewer Agent."""

    issue: IssueContext
    pr: PRContext
    ci_results: List[CIResult]
    previous_reviews: List[ReviewResult]


@dataclass
class CodeAgentContext:
    """Контекст для Code Agent."""

    issue: IssueContext
    repository_path: str
    branch: str
    previous_review_feedback: Optional[str] = None
    iteration_number: int = 1


@dataclass
class AgentExecutionResult:
    """Результат выполнения агента."""

    success: bool
    message: str
    pr_number: Optional[int] = None
    branch: Optional[str] = None
    changes: List[CodeChange] = None

    def __post_init__(self):
        """Инициализация после создания."""
        if self.changes is None:
            self.changes = []


@dataclass
class IterationState:
    """Состояние итерации разработки."""

    issue_number: int
    repository: str
    current_iteration: int
    pr_number: Optional[int] = None
    branch: Optional[str] = None
    last_review_verdict: Optional[ReviewVerdict] = None
    completed: bool = False
