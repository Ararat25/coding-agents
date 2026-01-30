"""CLI интерфейс для coding-agents."""

import logging
import sys

import click
import structlog

from coding_agents.config import settings
from coding_agents.infrastructure.github_client import GitHubClient
from coding_agents.infrastructure.llm_client import create_llm_client
from coding_agents.orchestration.sdlc_orchestrator import SDLCOrchestrator
from coding_agents.services.code_agent import CodeAgentService
from coding_agents.services.reviewer_agent import ReviewerAgentService
from coding_agents.utils import normalize_repo

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = structlog.get_logger()


@click.group()
@click.version_option(version="0.1.0")
def main():
    """Coding Agents - автоматизированная агентная система для разработки в GitHub."""
    pass


@main.command()
@click.option(
    "--repo",
    required=True,
    help="Репозиторий: owner/repo или URL (https://github.com/owner/repo)",
)
@click.option("--issue", "issue_number", required=True, type=int, help="Номер Issue")
@click.option("--iteration", "start_iteration", default=1, type=int, help="Начальная итерация")
def process_issue(repo: str, issue_number: int, start_iteration: int):
    """Обработать Issue полностью (Code Agent + Reviewer + итерации)."""
    try:
        repo = normalize_repo(repo)
        logger.info("Инициализация компонентов", repo=repo, issue=issue_number)

        # Инициализация клиентов
        github_client = GitHubClient()
        llm_client = create_llm_client()
        code_agent = CodeAgentService(github_client, llm_client)
        reviewer_agent = ReviewerAgentService(github_client, llm_client)

        # Оркестратор
        orchestrator = SDLCOrchestrator(github_client, code_agent, reviewer_agent)

        # Запуск
        logger.info("Запуск обработки Issue", repo=repo, issue=issue_number)
        result = orchestrator.process_issue(repo, issue_number, start_iteration)

        if result["success"]:
            click.echo(f"✅ {result['message']}")
            click.echo(f"Итераций выполнено: {result['iteration']}")
            if result.get("state", {}).pr_number:
                click.echo(f"PR: #{result['state'].pr_number}")
            sys.exit(0)
        else:
            click.echo(f"❌ {result['message']}", err=True)
            sys.exit(1)

    except Exception as e:
        logger.error("Ошибка выполнения", error=str(e), exc_info=True)
        click.echo(f"❌ Ошибка: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option(
    "--repo",
    required=True,
    help="Репозиторий: owner/repo или URL (https://github.com/owner/repo)",
)
@click.option("--issue", "issue_number", required=True, type=int, help="Номер Issue")
@click.option("--branch", help="Ветка для работы (опционально)")
@click.option("--pr", "pr_number", type=int, help="Номер PR для обновления (опционально)")
@click.option("--iteration", default=1, type=int, help="Номер итерации")
def code_agent(repo: str, issue_number: int, branch: str, pr_number: int, iteration: int):
    """Запустить только Code Agent."""
    try:
        repo = normalize_repo(repo)
        logger.info("Инициализация Code Agent", repo=repo, issue=issue_number)

        github_client = GitHubClient()
        llm_client = create_llm_client()
        code_agent_service = CodeAgentService(github_client, llm_client)

        result = code_agent_service.execute(
            repo=repo,
            issue_number=issue_number,
            branch=branch,
            pr_number=pr_number,
            iteration_number=iteration,
        )

        if result.success:
            click.echo(f"✅ {result.message}")
            if result.pr_number:
                click.echo(f"PR: #{result.pr_number}")
            if result.branch:
                click.echo(f"Ветка: {result.branch}")
            sys.exit(0)
        else:
            click.echo(f"❌ {result.message}", err=True)
            sys.exit(1)

    except Exception as e:
        logger.error("Ошибка выполнения Code Agent", error=str(e), exc_info=True)
        click.echo(f"❌ Ошибка: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option(
    "--repo",
    required=True,
    help="Репозиторий: owner/repo или URL (https://github.com/owner/repo)",
)
@click.option("--pr", "pr_number", required=True, type=int, help="Номер Pull Request")
@click.option("--wait-ci/--no-wait-ci", default=True, help="Ждать завершения CI")
def reviewer(repo: str, pr_number: int, wait_ci: bool):
    """Запустить только Reviewer Agent."""
    try:
        repo = normalize_repo(repo)
        logger.info("Инициализация Reviewer Agent", repo=repo, pr=pr_number)

        github_client = GitHubClient()
        llm_client = create_llm_client()
        reviewer_service = ReviewerAgentService(github_client, llm_client)

        review_result = reviewer_service.execute(
            repo=repo,
            pr_number=pr_number,
            wait_for_ci=wait_ci,
        )

        # Публикуем review
        reviewer_service.publish_review(repo, pr_number, review_result)

        click.echo(f"✅ Review завершён. Вердикт: {review_result.verdict.value}")
        click.echo(f"Резюме: {review_result.summary}")
        click.echo(f"Комментариев: {len(review_result.comments)}")
        sys.exit(0)

    except Exception as e:
        logger.error("Ошибка выполнения Reviewer Agent", error=str(e), exc_info=True)
        click.echo(f"❌ Ошибка: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
