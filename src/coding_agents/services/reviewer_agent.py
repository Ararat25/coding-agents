"""Reviewer Agent - сервис для анализа Pull Request."""

import logging
import time
from typing import List, Optional

from coding_agents.config import settings
from coding_agents.domain.interfaces import GitHubClientInterface, LLMClientInterface
from coding_agents.domain.models import CIResult, ReviewComment, ReviewResult, ReviewVerdict
from coding_agents.prompts.reviewer_prompts import (
    get_reviewer_response_format,
    get_reviewer_system_prompt,
    get_reviewer_user_prompt,
)

logger = logging.getLogger(__name__)


class ReviewerAgentService:
    """Сервис Reviewer Agent."""

    def __init__(
        self,
        github_client: GitHubClientInterface,
        llm_client: LLMClientInterface,
    ):
        """Инициализация сервиса."""
        self.github_client = github_client
        self.llm_client = llm_client

    def execute(
        self,
        repo: str,
        pr_number: int,
        wait_for_ci: bool = True,
        max_ci_wait_time: int = 300,
    ) -> ReviewResult:
        """Выполнить анализ Pull Request."""
        start_time = time.time()
        timeout = settings.reviewer_timeout

        try:
            # Получаем PR
            logger.info(f"Получение PR #{pr_number} из {repo}")
            pr = self.github_client.get_pr(repo, pr_number)

            # Получаем связанный Issue (пытаемся найти по номеру в описании или по ветке)
            issue = self._find_related_issue(repo, pr)

            # Получаем результаты CI
            logger.info(f"Получение результатов CI для коммита {pr.head_sha}")
            ci_results = self.github_client.get_ci_results(repo, pr.head_sha)

            # Если нужно ждать CI и он ещё не завершён
            if wait_for_ci and self._has_pending_ci(ci_results):
                logger.info("Ожидание завершения CI проверок...")
                ci_results = self._wait_for_ci_completion(
                    repo,
                    pr.head_sha,
                    ci_results,
                    max_wait_time=max_ci_wait_time,
                )

            # Получаем предыдущие reviews
            previous_reviews = self.github_client.get_pr_reviews(repo, pr_number)

            # Проверяем таймаут
            if time.time() - start_time > timeout:
                return ReviewResult(
                    verdict=ReviewVerdict.COMMENT,
                    summary="Превышен таймаут анализа. Проверка выполнена частично.",
                    comments=[],
                    general_feedback="Таймаут анализа. Рекомендуется ручная проверка.",
                )

            # Формируем промпт
            system_prompt = get_reviewer_system_prompt()
            user_prompt = get_reviewer_user_prompt(
                issue_title=issue.title,
                issue_body=issue.body,
                pr_title=pr.title,
                pr_body=pr.body,
                diff=pr.diff,
                files_changed=pr.files_changed,
                ci_results=ci_results,
                previous_reviews=previous_reviews if previous_reviews else None,
            )

            # Вызываем LLM
            logger.info(f"Анализ PR #{pr_number} с помощью LLM")
            response_format = get_reviewer_response_format()
            llm_response = self.llm_client.generate_structured(
                prompt=user_prompt,
                system_prompt=system_prompt,
                response_format=response_format,
            )

            # Парсим ответ
            verdict_str = llm_response.get("verdict", "comment")
            verdict = ReviewVerdict.COMMENT
            if verdict_str == "approved":
                verdict = ReviewVerdict.APPROVED
            elif verdict_str == "changes_requested":
                verdict = ReviewVerdict.CHANGES_REQUESTED

            summary = llm_response.get("summary", "Проверка выполнена")
            general_feedback = llm_response.get("general_feedback")

            # Преобразуем комментарии
            comments_data = llm_response.get("comments", [])
            comments = []
            for comment_data in comments_data:
                try:
                    comment = ReviewComment(
                        file_path=comment_data["file_path"],
                        line_number=comment_data["line_number"],
                        comment=comment_data["comment"],
                        suggestion=comment_data.get("suggestion"),
                    )
                    comments.append(comment)
                except KeyError as e:
                    logger.warning(f"Пропущен некорректный комментарий: {e}")
                    continue

            result = ReviewResult(
                verdict=verdict,
                summary=summary,
                comments=comments,
                general_feedback=general_feedback,
            )

            logger.info(f"Review завершён. Вердикт: {verdict.value}")

            return result

        except Exception as e:
            logger.error(f"Ошибка выполнения Reviewer Agent: {e}", exc_info=True)
            return ReviewResult(
                verdict=ReviewVerdict.COMMENT,
                summary=f"Ошибка при анализе: {str(e)}",
                comments=[],
                general_feedback="Произошла ошибка при автоматическом анализе. Требуется ручная проверка.",
            )

    def publish_review(
        self,
        repo: str,
        pr_number: int,
        review_result: ReviewResult,
    ) -> None:
        """Опубликовать результаты review в PR."""
        try:
            # Формируем тело review
            body_parts = []
            
            # Добавляем заголовок с вердиктом
            if review_result.verdict == ReviewVerdict.APPROVED:
                body_parts.append("✅ **Код готов к approve**")
                body_parts.append("\nАвтоматическая проверка завершена успешно. Ожидается окончательный approve от человека.\n")
            elif review_result.verdict == ReviewVerdict.CHANGES_REQUESTED:
                body_parts.append("❌ **Требуются изменения**\n")
            else:
                body_parts.append("💬 **Комментарий к review**\n")
            
            body_parts.append(review_result.summary)

            if review_result.general_feedback:
                body_parts.append(f"\n**Общий фидбек:**\n{review_result.general_feedback}")

            if review_result.comments:
                body_parts.append(f"\n**Комментарии к коду ({len(review_result.comments)}):**")
                for comment in review_result.comments:
                    body_parts.append(
                        f"\n- `{comment.file_path}:{comment.line_number}`: {comment.comment}"
                    )
                    if comment.suggestion:
                        body_parts.append(f"  💡 Предложение: {comment.suggestion}")

            body = "\n".join(body_parts)

            # Определяем event для GitHub
            # Агент НЕ может делать APPROVE или REQUEST_CHANGES своего собственного PR
            # GitHub API запрещает это. Мы используем COMMENT для всех случаев.
            event = "COMMENT"

            # Формируем комментарии для review (line comments)
            review_comments = []
            for comment in review_result.comments:
                review_comments.append(
                    {
                        "file_path": comment.file_path,
                        "line_number": comment.line_number,
                        "comment": comment.comment + (f"\n\n💡 {comment.suggestion}" if comment.suggestion else ""),
                    }
                )

            # Создаём review
            self.github_client.create_review(
                repo=repo,
                pr_number=pr_number,
                body=body,
                event=event,
                comments=review_comments if review_comments else None,
            )

            logger.info(f"Review опубликован для PR #{pr_number} с вердиктом {event}")

        except Exception as e:
            logger.error(f"Ошибка при публикации review: {e}", exc_info=True)
            raise

    def _find_related_issue(self, repo: str, pr) -> "IssueContext":
        """Найти связанный Issue для PR."""
        # Пытаемся найти номер Issue в описании PR или в ветке
        import re

        # Ищем в описании PR
        issue_match = re.search(r"#(\d+)", pr.body or "")
        if issue_match:
            issue_number = int(issue_match.group(1))
            try:
                return self.github_client.get_issue(repo, issue_number)
            except Exception:
                pass

        # Ищем в названии ветки
        branch_match = re.search(r"issue-(\d+)", pr.head_branch)
        if branch_match:
            issue_number = int(branch_match.group(1))
            try:
                return self.github_client.get_issue(repo, issue_number)
            except Exception:
                pass

        # Если не нашли, создаём фиктивный Issue из PR
        from coding_agents.domain.models import IssueContext
        from datetime import datetime

        return IssueContext(
            number=0,
            title=pr.title,
            body=pr.body or "",
            labels=[],
            state="open",
            created_at=pr.created_at,
            updated_at=pr.updated_at,
        )

    def _has_pending_ci(self, ci_results: List[CIResult]) -> bool:
        """Проверить есть ли незавершённые CI проверки."""
        from coding_agents.domain.models import CIStatus

        return any(ci.status == CIStatus.PENDING for ci in ci_results)

    def _wait_for_ci_completion(
        self,
        repo: str,
        sha: str,
        initial_ci_results: List[CIResult],
        max_wait_time: int = 300,
        check_interval: int = 10,
    ) -> List[CIResult]:
        """Ожидать завершения CI проверок."""
        import time

        start_time = time.time()
        ci_results = initial_ci_results

        while time.time() - start_time < max_wait_time:
            if not self._has_pending_ci(ci_results):
                logger.info("Все CI проверки завершены")
                break

            time.sleep(check_interval)
            ci_results = self.github_client.get_ci_results(repo, sha)

        return ci_results
