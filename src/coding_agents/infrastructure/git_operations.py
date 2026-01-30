"""Операции с Git репозиториями."""

import logging
import os
import shutil
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

from git import Actor, Repo
from git.exc import GitError

from coding_agents.config import settings
from coding_agents.domain.interfaces import GitOperationsInterface
from coding_agents.domain.models import CodeChange

logger = logging.getLogger(__name__)


class GitOperations(GitOperationsInterface):
    """Реализация операций с Git."""

    def __init__(self, base_repos_dir: Optional[str] = None):
        """Инициализация."""
        base_dir = base_repos_dir or "repos"
        self.base_repos_dir = Path(base_dir) if isinstance(base_dir, str) else base_dir
        self.base_repos_dir.mkdir(parents=True, exist_ok=True)

    def clone_repository(self, repo_url: str, local_path: str, token: str) -> None:
        """Клонировать репозиторий."""
        try:
            # Формируем URL с токеном
            parsed = urlparse(repo_url)
            if "github.com" in parsed.netloc:
                # Для GitHub используем формат с токеном
                if not repo_url.startswith("https://"):
                    repo_url = f"https://{repo_url}"
                auth_url = repo_url.replace("https://", f"https://{token}@")
            else:
                auth_url = repo_url

            full_path = self.base_repos_dir / local_path

            # Удаляем существующий клон если есть
            if full_path.exists():
                shutil.rmtree(full_path)

            Repo.clone_from(auth_url, str(full_path))
            logger.info(f"Репозиторий клонирован в {full_path}")
        except GitError as e:
            logger.error(f"Ошибка при клонировании репозитория {repo_url}: {e}")
            raise

    def checkout_branch(self, repo_path: str, branch: str, create: bool = False) -> None:
        """Переключиться на ветку. Если create=True и ветка уже есть — просто переключаемся."""
        try:
            full_path = self.base_repos_dir / repo_path
            repo = Repo(str(full_path))

            if create:
                local_branch_names = [h.name for h in repo.heads]
                if branch in local_branch_names:
                    repo.git.checkout(branch)
                else:
                    repo.git.checkout("-b", branch)
            else:
                repo.git.checkout(branch)

            logger.info(f"Переключено на ветку {branch} в {repo_path}")
        except GitError as e:
            logger.error(f"Ошибка при переключении на ветку {branch} в {repo_path}: {e}")
            raise

    def apply_changes(
        self,
        repo_path: str,
        changes: List[CodeChange],
    ) -> None:
        """Применить изменения к репозиторию."""
        try:
            full_path = self.base_repos_dir / repo_path
            repo_path_obj = Path(full_path)

            for change in changes:
                file_path = repo_path_obj / change.file_path

                if change.operation == "delete":
                    if file_path.exists():
                        file_path.unlink()
                        logger.info(f"Удалён файл {change.file_path}")
                elif change.operation == "create":
                    # Создаём директорию если нужно
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(change.content or "")
                    logger.info(f"Создан файл {change.file_path}")
                elif change.operation == "modify":
                    if file_path.exists():
                        # Если указаны строки, делаем точечное редактирование
                        if change.line_start and change.line_end and change.old_content:
                            with open(file_path, "r", encoding="utf-8") as f:
                                lines = f.readlines()

                            # Заменяем строки
                            start_idx = change.line_start - 1
                            end_idx = change.line_end

                            new_lines = lines[:start_idx]
                            if change.content:
                                new_lines.extend(change.content.splitlines(keepends=True))
                            new_lines.extend(lines[end_idx:])

                            with open(file_path, "w", encoding="utf-8") as f:
                                f.writelines(new_lines)
                        else:
                            # Полная замена файла
                            with open(file_path, "w", encoding="utf-8") as f:
                                f.write(change.content or "")
                        logger.info(f"Изменён файл {change.file_path}")
                    else:
                        # Файл не существует, создаём
                        file_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(change.content or "")
                        logger.info(f"Создан файл {change.file_path} (при модификации)")

        except Exception as e:
            logger.error(f"Ошибка при применении изменений в {repo_path}: {e}")
            raise

    def commit_changes(
        self,
        repo_path: str,
        message: str,
        author_name: str = "Code Agent",
        author_email: str = "code-agent@example.com",
    ) -> str:
        """Закоммитить изменения. Возвращает SHA коммита."""
        try:
            full_path = self.base_repos_dir / repo_path
            repo = Repo(str(full_path))

            # Добавляем все изменения
            repo.git.add(A=True)

            # Проверяем есть ли изменения
            if repo.is_dirty() or repo.untracked_files:
                author = Actor(author_name, author_email)
                repo.index.commit(
                    message,
                    author=author,
                    committer=author,
                )
                commit_sha = repo.head.commit.hexsha
                logger.info(f"Изменения закоммичены в {repo_path}: {commit_sha}")
                return commit_sha
            else:
                logger.warning(f"Нет изменений для коммита в {repo_path}")
                return repo.head.commit.hexsha
        except GitError as e:
            logger.error(f"Ошибка при коммите в {repo_path}: {e}")
            raise

    def push_changes(
        self,
        repo_path: str,
        branch: str,
        remote: str = "origin",
        token: str = None,
    ) -> None:
        """Запушить изменения."""
        try:
            full_path = self.base_repos_dir / repo_path
            repo = Repo(str(full_path))

            # Настраиваем remote с токеном если нужно
            if token:
                origin = repo.remotes[remote]
                url = origin.url
                parsed = urlparse(url)
                if "github.com" in parsed.netloc and token not in url:
                    auth_url = url.replace("https://", f"https://{token}@")
                    origin.set_url(auth_url)

            repo.git.push(remote, branch, force=False)
            logger.info(f"Изменения запушены в {remote}/{branch} для {repo_path}")
        except GitError as e:
            logger.error(f"Ошибка при push в {repo_path}: {e}")
            raise

    def get_default_branch(self, repo_path: str) -> str:
        """Получить дефолтную ветку репозитория."""
        try:
            full_path = self.base_repos_dir / repo_path
            repo = Repo(str(full_path))

            # Пробуем получить из remote
            try:
                remote_ref = repo.remotes.origin.refs.HEAD
                return remote_ref.ref.name.split("/")[-1]
            except:
                # Пробуем main или master
                for branch in ["main", "master"]:
                    try:
                        repo.git.show_ref(f"refs/heads/{branch}")
                        return branch
                    except:
                        continue

            # Если ничего не найдено, возвращаем main по умолчанию
            return "main"
        except Exception as e:
            logger.warning(f"Не удалось определить дефолтную ветку для {repo_path}: {e}")
            return "main"
