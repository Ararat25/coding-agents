"""FastAPI сервер для API и webhook."""

import hashlib
import hmac
import json
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from coding_agents.config import settings
from coding_agents.infrastructure.github_client import GitHubClient
from coding_agents.infrastructure.llm_client import create_llm_client
from coding_agents.orchestration.sdlc_orchestrator import SDLCOrchestrator
from coding_agents.services.code_agent import CodeAgentService
from coding_agents.services.reviewer_agent import ReviewerAgentService
from coding_agents.utils import normalize_repo

logger = logging.getLogger(__name__)

# Глобальные сервисы (инициализируются при старте)
github_client: Optional[GitHubClient] = None
code_agent: Optional[CodeAgentService] = None
reviewer_agent: Optional[ReviewerAgentService] = None
orchestrator: Optional[SDLCOrchestrator] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Инициализация и завершение сервисов."""
    global github_client, code_agent, reviewer_agent, orchestrator
    logger.info("Инициализация сервисов")
    github_client = GitHubClient()
    llm_client = create_llm_client()
    code_agent = CodeAgentService(github_client, llm_client)
    reviewer_agent = ReviewerAgentService(github_client, llm_client)
    orchestrator = SDLCOrchestrator(github_client, code_agent, reviewer_agent)
    logger.info("Сервисы инициализированы")
    yield
    # shutdown при необходимости


app = FastAPI(title="Coding Agents API", version="0.1.0", lifespan=lifespan)


# Pydantic модели для запросов
class ProcessIssueRequest(BaseModel):
    """Запрос на обработку Issue."""

    repo: str
    issue_number: int
    start_iteration: int = 1


class CodeAgentRequest(BaseModel):
    """Запрос на выполнение Code Agent."""

    repo: str
    issue_number: int
    branch: Optional[str] = None
    pr_number: Optional[int] = None
    iteration_number: int = 1


class ReviewerRequest(BaseModel):
    """Запрос на выполнение Reviewer Agent."""

    repo: str
    pr_number: int
    wait_for_ci: bool = True


@app.get("/health")
async def health():
    """Проверка здоровья сервиса."""
    return {"status": "ok"}


@app.post("/api/process-issue")
async def api_process_issue(request: ProcessIssueRequest):
    """API endpoint для обработки Issue."""
    try:
        repo = normalize_repo(request.repo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        result = orchestrator.process_issue(
            repo=repo,
            issue_number=request.issue_number,
            start_iteration=request.start_iteration,
        )

        return {
            "success": result["success"],
            "message": result["message"],
            "iteration": result["iteration"],
            "pr_number": result.get("state", {}).pr_number if result.get("state") else None,
        }
    except Exception as e:
        logger.error(f"Ошибка обработки Issue: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/code-agent")
async def api_code_agent(request: CodeAgentRequest):
    """API endpoint для Code Agent."""
    try:
        repo = normalize_repo(request.repo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        result = code_agent.execute(
            repo=repo,
            issue_number=request.issue_number,
            branch=request.branch,
            pr_number=request.pr_number,
            iteration_number=request.iteration_number,
        )

        return {
            "success": result.success,
            "message": result.message,
            "pr_number": result.pr_number,
            "branch": result.branch,
        }
    except Exception as e:
        logger.error(f"Ошибка выполнения Code Agent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/reviewer")
async def api_reviewer(request: ReviewerRequest):
    """API endpoint для Reviewer Agent."""
    try:
        repo = normalize_repo(request.repo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        review_result = reviewer_agent.execute(
            repo=repo,
            pr_number=request.pr_number,
            wait_for_ci=request.wait_for_ci,
        )

        # Публикуем review
        reviewer_agent.publish_review(repo, request.pr_number, review_result)

        return {
            "success": True,
            "verdict": review_result.verdict.value,
            "summary": review_result.summary,
            "comments_count": len(review_result.comments),
        }
    except Exception as e:
        logger.error(f"Ошибка выполнения Reviewer Agent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def verify_webhook_signature(payload_body: bytes, signature_header: str, secret: str) -> bool:
    """Проверить подпись webhook от GitHub."""
    if not secret:
        logger.warning("Webhook secret не установлен, пропускаем проверку подписи")
        return True

    hash_object = hmac.new(secret.encode("utf-8"), msg=payload_body, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()

    return hmac.compare_digest(expected_signature, signature_header)


@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(..., alias="X-GitHub-Event"),
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
):
    """Webhook endpoint для GitHub событий."""
    try:
        payload_body = await request.body()

        # Проверяем подпись
        if settings.webhook_secret and x_hub_signature_256:
            if not verify_webhook_signature(payload_body, x_hub_signature_256, settings.webhook_secret):
                logger.warning("Неверная подпись webhook")
                raise HTTPException(status_code=403, detail="Invalid signature")

        payload = json.loads(payload_body.decode("utf-8"))
        action = payload.get("action")

        logger.info(f"Получен webhook: {x_github_event}, action: {action}")

        # Обработка событий
        if x_github_event == "issues" and action == "opened":
            # Новый Issue - запускаем Code Agent
            issue = payload.get("issue", {})
            repository = payload.get("repository", {})
            repo = repository.get("full_name")

            if repo and issue.get("number"):
                issue_number = issue["number"]
                logger.info(f"Обработка нового Issue #{issue_number} из {repo}")

                # Запускаем в фоне (можно использовать background tasks FastAPI)
                result = orchestrator.process_issue(repo, issue_number)

                return {
                    "success": result["success"],
                    "message": f"Обработка Issue #{issue_number} запущена",
                }

        elif x_github_event == "pull_request":
            pr = payload.get("pull_request", {})
            repository = payload.get("repository", {})
            repo = repository.get("full_name")

            if action in ("opened", "synchronize") and pr.get("number") and repo:
                pr_number = pr["number"]
                logger.info(f"Обработка PR #{pr_number} из {repo}")

                # Запускаем Reviewer
                review_result = reviewer_agent.execute(
                    repo=repo,
                    pr_number=pr_number,
                    wait_for_ci=True,
                )

                reviewer_agent.publish_review(repo, pr_number, review_result)

                # Если changes_requested и PR от нашего бота - запускаем следующую итерацию
                if (
                    review_result.verdict.value == "changes_requested"
                    and pr.get("user", {}).get("type") == "Bot"
                ):
                    # Находим связанный Issue
                    issue_match = None
                    pr_body = pr.get("body", "")
                    import re

                    issue_match = re.search(r"#(\d+)", pr_body)
                    if issue_match:
                        issue_number = int(issue_match.group(1))
                        logger.info(f"Запуск следующей итерации для Issue #{issue_number}")
                        orchestrator.process_issue(repo, issue_number)

                return {
                    "success": True,
                    "message": f"Review для PR #{pr_number} выполнен",
                    "verdict": review_result.verdict.value,
                }

        elif x_github_event == "check_suite" and action == "completed":
            # CI завершён - можно запустить Reviewer если PR ещё не проверен
            check_suite = payload.get("check_suite", {})
            repository = payload.get("repository", {})
            repo = repository.get("full_name")
            head_sha = check_suite.get("head_sha")

            if repo and head_sha:
                # Находим PR по SHA
                # (упрощённо, в реальности нужно искать PR по head_sha)
                logger.info(f"CI завершён для {head_sha} в {repo}")

        return {"success": True, "message": "Webhook обработан"}

    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"Ошибка обработки webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.webhook_port)
