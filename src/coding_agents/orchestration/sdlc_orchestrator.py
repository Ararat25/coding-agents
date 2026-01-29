"""Оркестратор SDLC процесса."""

import logging
from typing import Optional

from coding_agents.config import settings
from coding_agents.domain.interfaces import GitHubClientInterface
from coding_agents.domain.models import IterationState, PRContext, ReviewVerdict
from coding_agents.services.code_agent import CodeAgentService
from coding_agents.services.reviewer_agent import ReviewerAgentService

logger = logging.getLogger(__name__)


class SDLCOrchestrator:
    """Оркестратор полного цикла SDLC."""

    def __init__(
        self,
        github_client: GitHubClientInterface,
        code_agent: CodeAgentService,
        reviewer_agent: ReviewerAgentService,
    ):
        """Инициализация оркестратора."""
        self.github_client = github_client
        self.code_agent = code_agent
        self.reviewer_agent = reviewer_agent
        self.max_iterations = settings.max_iterations

    def process_issue(
        self,
        repo: str,
        issue_number: int,
        start_iteration: int = 1,
    ) -> dict:
        """Обработать Issue полностью (Issue → Code → Review → итерации)."""
        logger.info(f"Начало обработки Issue #{issue_number} из {repo}")

        state = IterationState(
            issue_number=issue_number,
            repository=repo,
            current_iteration=start_iteration,
        )

        # Проверяем есть ли уже PR для этого Issue
        existing_pr = self._find_existing_pr(repo, issue_number)
        if existing_pr:
            state.pr_number = existing_pr.number
            state.branch = existing_pr.head_branch
            logger.info(f"Найден существующий PR #{existing_pr.number} для Issue #{issue_number}")

        iteration = start_iteration

        while iteration <= self.max_iterations and not state.completed:
            logger.info(f"Итерация {iteration}/{self.max_iterations} для Issue #{issue_number}")

            # Шаг 1: Code Agent
            if iteration == start_iteration or state.last_review_verdict == ReviewVerdict.CHANGES_REQUESTED:
                # Получаем предыдущий фидбек если есть
                previous_feedback = None
                if iteration > 1 and state.pr_number:
                    previous_feedback = self._get_last_review_feedback(repo, state.pr_number)

                result = self.code_agent.execute(
                    repo=repo,
                    issue_number=issue_number,
                    branch=state.branch,
                    pr_number=state.pr_number,
                    previous_feedback=previous_feedback,
                    iteration_number=iteration,
                )

                if not result.success:
                    logger.error(f"Code Agent не смог выполнить задачу: {result.message}")
                    return {
                        "success": False,
                        "message": f"Code Agent ошибка: {result.message}",
                        "iteration": iteration,
                        "state": state,
                    }

                # Обновляем состояние
                if result.pr_number:
                    state.pr_number = result.pr_number
                if result.branch:
                    state.branch = result.branch

                logger.info(f"Code Agent завершил итерацию {iteration}. PR #{state.pr_number}")

            # Шаг 2: Reviewer Agent
            if state.pr_number:
                logger.info(f"Запуск Reviewer для PR #{state.pr_number}")
                review_result = self.reviewer_agent.execute(
                    repo=repo,
                    pr_number=state.pr_number,
                    wait_for_ci=True,
                )

                # Публикуем review
                self.reviewer_agent.publish_review(
                    repo=repo,
                    pr_number=state.pr_number,
                    review_result=review_result,
                )

                state.last_review_verdict = review_result.verdict

                logger.info(
                    f"Review завершён. Вердикт: {review_result.verdict.value}. "
                    f"Комментариев: {len(review_result.comments)}"
                )

                # Проверяем завершение
                if review_result.verdict == ReviewVerdict.APPROVED:
                    state.completed = True
                    logger.info(f"Issue #{issue_number} успешно завершено на итерации {iteration}")
                    return {
                        "success": True,
                        "message": f"Задача успешно выполнена. PR #{state.pr_number} одобрен.",
                        "iteration": iteration,
                        "state": state,
                        "review_result": review_result,
                    }
                elif review_result.verdict == ReviewVerdict.CHANGES_REQUESTED:
                    # Нужна следующая итерация
                    logger.info(f"Требуются изменения. Переход к итерации {iteration + 1}")
                    iteration += 1
                    state.current_iteration = iteration
                    continue
                else:
                    # COMMENT - нейтральный вердикт, можно считать завершённым или продолжить
                    logger.info("Review с вердиктом COMMENT. Завершаем процесс.")
                    state.completed = True
                    return {
                        "success": True,
                        "message": f"Review завершён с комментариями. PR #{state.pr_number}.",
                        "iteration": iteration,
                        "state": state,
                        "review_result": review_result,
                    }
            else:
                logger.error("PR номер не установлен после выполнения Code Agent")
                return {
                    "success": False,
                    "message": "PR не был создан",
                    "iteration": iteration,
                    "state": state,
                }

        # Достигнут лимит итераций
        if iteration > self.max_iterations:
            logger.warning(
                f"Достигнут лимит итераций ({self.max_iterations}) для Issue #{issue_number}"
            )
            # Оставляем комментарий в Issue
            self.github_client.create_comment(
                repo=repo,
                issue_number=issue_number,
                body=(
                    f"⚠️ Достигнут лимит итераций ({self.max_iterations}). "
                    f"Процесс автоматической разработки остановлен. "
                    f"Текущий PR: #{state.pr_number if state.pr_number else 'не создан'}"
                ),
            )

        return {
            "success": False,
            "message": f"Достигнут лимит итераций ({self.max_iterations})",
            "iteration": iteration - 1,
            "state": state,
        }

    def _find_existing_pr(self, repo: str, issue_number: int) -> Optional[PRContext]:
        """Найти существующий PR для Issue."""
        # Пытаемся найти PR по ветке issue-{number}
        branch_patterns = [
            f"issue-{issue_number}",
            f"issue-{issue_number}-iter-",
        ]

        for pattern in branch_patterns:
            pr = self.github_client.get_pr_by_branch(repo, pattern)
            if pr:
                return pr

        return None

    def _get_last_review_feedback(self, repo: str, pr_number: int) -> Optional[str]:
        """Получить фидбек из последнего review."""
        try:
            reviews = self.github_client.get_pr_reviews(repo, pr_number)
            if reviews:
                # Берём последний review с changes_requested
                for review in reversed(reviews):
                    if review.get("state") == "CHANGES_REQUESTED":
                        return review.get("body", "")
                # Если нет changes_requested, берём последний
                if reviews:
                    return reviews[-1].get("body", "")
        except Exception as e:
            logger.warning(f"Ошибка при получении последнего review: {e}")

        return None
