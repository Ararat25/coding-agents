"""Клиент для работы с GitHub API."""

import logging
from datetime import datetime
from typing import List, Optional

from github import Github, GithubException
from github.PullRequest import PullRequest
from github.Issue import Issue

from coding_agents.config import settings
from coding_agents.domain.interfaces import GitHubClientInterface
from coding_agents.domain.models import CIResult, CIStatus, IssueContext, PRContext

logger = logging.getLogger(__name__)


class GitHubClient(GitHubClientInterface):
    """Реализация клиента GitHub API."""

    def __init__(self, token: Optional[str] = None):
        """Инициализация клиента."""
        self.token = token or settings.get_github_token()
        self.github = Github(self.token)
        self._cache = {}

    def get_issue(self, repo: str, issue_number: int) -> IssueContext:
        """Получить Issue по номеру."""
        try:
            repository = self.github.get_repo(repo)
            issue = repository.get_issue(issue_number)

            return IssueContext(
                number=issue.number,
                title=issue.title,
                body=issue.body or "",
                labels=[label.name for label in issue.labels],
                state=issue.state,
                created_at=issue.created_at,
                updated_at=issue.updated_at,
            )
        except GithubException as e:
            logger.error(f"Ошибка при получении Issue {issue_number} из {repo}: {e}")
            raise

    def get_pr(self, repo: str, pr_number: int) -> PRContext:
        """Получить Pull Request по номеру."""
        try:
            repository = self.github.get_repo(repo)
            pr = repository.get_pull(pr_number)

            return self._pr_to_context(pr, repo)
        except GithubException as e:
            logger.error(f"Ошибка при получении PR {pr_number} из {repo}: {e}")
            raise

    def get_pr_by_branch(self, repo: str, branch: str) -> Optional[PRContext]:
        """Получить Pull Request по ветке."""
        try:
            repository = self.github.get_repo(repo)
            pulls = repository.get_pulls(head=f"{repository.owner.login}:{branch}", state="open")

            for pr in pulls:
                if pr.head.ref == branch:
                    return self._pr_to_context(pr, repo)
            return None
        except GithubException as e:
            logger.error(f"Ошибка при получении PR по ветке {branch} из {repo}: {e}")
            return None

    def get_ci_results(self, repo: str, sha: str) -> List[CIResult]:
        """Получить результаты CI для коммита."""
        try:
            repository = self.github.get_repo(repo)
            commit = repository.get_commit(sha)

            ci_results = []

            # Получаем статусы коммита
            statuses = commit.get_statuses()
            for status in statuses:
                ci_status = CIStatus.SUCCESS if status.state == "success" else CIStatus.FAILURE
                if status.state == "pending":
                    ci_status = CIStatus.PENDING
                elif status.state == "error":
                    ci_status = CIStatus.ERROR

                ci_results.append(
                    CIResult(
                        name=status.context,
                        status=ci_status,
                        conclusion=status.state,
                        url=status.target_url,
                        details=status.description,
                    )
                )

            # Получаем check runs
            check_runs = commit.get_check_runs()
            for check_run in check_runs:
                conclusion = check_run.conclusion
                status = CIStatus.PENDING
                if conclusion == "success":
                    status = CIStatus.SUCCESS
                elif conclusion in ("failure", "cancelled"):
                    status = CIStatus.FAILURE
                elif conclusion == "error":
                    status = CIStatus.ERROR

                ci_results.append(
                    CIResult(
                        name=check_run.name,
                        status=status,
                        conclusion=conclusion,
                        url=check_run.html_url,
                        details=check_run.output.get("summary") if check_run.output else None,
                    )
                )

            return ci_results
        except GithubException as e:
            logger.error(f"Ошибка при получении CI результатов для {sha} из {repo}: {e}")
            return []

    def create_pr(
        self,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str,
    ) -> int:
        """Создать Pull Request. Возвращает номер PR."""
        try:
            repository = self.github.get_repo(repo)
            pr = repository.create_pull(title=title, body=body, head=head, base=base)
            logger.info(f"Создан PR #{pr.number} в {repo}")
            return pr.number
        except GithubException as e:
            logger.error(f"Ошибка при создании PR в {repo}: {e}")
            raise

    def update_pr(self, repo: str, pr_number: int, body: Optional[str] = None) -> None:
        """Обновить Pull Request."""
        try:
            repository = self.github.get_repo(repo)
            pr = repository.get_pull(pr_number)
            if body:
                pr.edit(body=body)
            logger.info(f"Обновлён PR #{pr_number} в {repo}")
        except GithubException as e:
            logger.error(f"Ошибка при обновлении PR {pr_number} в {repo}: {e}")
            raise

    def create_review(
        self,
        repo: str,
        pr_number: int,
        body: str,
        event: str,
        comments: Optional[List[dict]] = None,
    ) -> None:
        """Создать review для PR."""
        try:
            repository = self.github.get_repo(repo)
            pr = repository.get_pull(pr_number)

            review_comments = None
            if comments:
                review_comments = [
                    {
                        "path": c["file_path"],
                        "position": c.get("line_number", 1),
                        "body": c["comment"],
                    }
                    for c in comments
                ]

            pr.create_review(body=body, event=event, comments=review_comments)
            logger.info(f"Создан review для PR #{pr_number} в {repo} с вердиктом {event}")
        except GithubException as e:
            logger.error(f"Ошибка при создании review для PR {pr_number} в {repo}: {e}")
            raise

    def create_comment(self, repo: str, issue_number: int, body: str) -> None:
        """Создать комментарий в Issue."""
        try:
            repository = self.github.get_repo(repo)
            issue = repository.get_issue(issue_number)
            issue.create_comment(body)
            logger.info(f"Создан комментарий в Issue #{issue_number} в {repo}")
        except GithubException as e:
            logger.error(f"Ошибка при создании комментария в Issue {issue_number} в {repo}: {e}")
            raise

    def create_pr_comment(self, repo: str, pr_number: int, body: str) -> None:
        """Создать комментарий в PR."""
        try:
            repository = self.github.get_repo(repo)
            pr = repository.get_pull(pr_number)
            pr.create_issue_comment(body)
            logger.info(f"Создан комментарий в PR #{pr_number} в {repo}")
        except GithubException as e:
            logger.error(f"Ошибка при создании комментария в PR {pr_number} в {repo}: {e}")
            raise

    def get_pr_reviews(self, repo: str, pr_number: int) -> List[dict]:
        """Получить список reviews для PR."""
        try:
            repository = self.github.get_repo(repo)
            pr = repository.get_pull(pr_number)
            reviews = pr.get_reviews()

            return [
                {
                    "id": review.id,
                    "body": review.body,
                    "state": review.state,
                    "user": review.user.login if review.user else None,
                    "submitted_at": review.submitted_at,
                }
                for review in reviews
            ]
        except GithubException as e:
            logger.error(f"Ошибка при получении reviews для PR {pr_number} в {repo}: {e}")
            return []

    def _pr_to_context(self, pr: PullRequest, repo: str) -> PRContext:
        """Преобразовать PR объект в контекст."""
        try:
            # Получаем diff
            diff = pr.diff_url
            # Для получения полного diff нужно сделать отдельный запрос
            files = pr.get_files()
            diff_content = ""
            files_changed = []

            for file in files:
                files_changed.append(file.filename)
                if file.patch:
                    diff_content += f"--- {file.filename}\n+++ {file.filename}\n{file.patch}\n"

            return PRContext(
                number=pr.number,
                title=pr.title,
                body=pr.body or "",
                head_branch=pr.head.ref,
                base_branch=pr.base.ref,
                head_sha=pr.head.sha,
                state=pr.state,
                diff=diff_content,
                files_changed=files_changed,
                created_at=pr.created_at,
                updated_at=pr.updated_at,
            )
        except Exception as e:
            logger.error(f"Ошибка при преобразовании PR в контекст: {e}")
            raise
