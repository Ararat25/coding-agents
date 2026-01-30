"""Утилиты."""

import re


def normalize_repo(repo: str) -> str:
    """
    Привести repo к формату owner/repo для GitHub API.

    Принимает:
    - owner/repo (без изменений)
    - URL: https://github.com/owner/repo
    - URL с путём: https://github.com/owner/repo/tree/main/some/path
    - URL без схемы: github.com/owner/repo

    Возвращает: owner/repo (только имя репозитория, без пути).
    """
    if not repo or not repo.strip():
        raise ValueError("repo не может быть пустым")

    repo = repo.strip()

    # Уже в формате owner/repo (нет слэшей кроме одного между owner и repo)
    if re.match(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$", repo):
        return repo

    # Убираем схему
    if "://" in repo:
        repo = repo.split("://", 1)[1]
    # Убираем ведущий www.
    if repo.lower().startswith("www."):
        repo = repo[4:]
    # Убираем host (github.com или git@github.com: при клонировании - но для API только github.com)
    if "github.com" in repo:
        repo = repo.split("github.com")[-1].strip("/")
    elif "github.com:" in repo:
        repo = repo.split("github.com:")[-1].strip("/")
    else:
        raise ValueError(
            f"Не удалось извлечь owner/repo из '{repo}'. "
            "Укажите репозиторий в формате owner/repo или полный URL GitHub, например: "
            "https://github.com/owner/repo"
        )

    # Убираем путь (tree/main/..., blob/..., и т.д.)
    if "/" in repo:
        parts = repo.split("/")
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
        if len(parts) == 1:
            raise ValueError(
                f"В URL указан только owner. Нужен формат owner/repo или URL вида "
                "https://github.com/owner/repo"
            )

    raise ValueError(
        f"Не удалось извлечь owner/repo из исходной строки. "
        "Используйте формат owner/repo или URL: https://github.com/owner/repo"
    )
