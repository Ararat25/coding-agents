"""Конфигурация приложения."""

import os
from enum import Enum
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    """Провайдеры LLM."""

    OPENAI = "openai"
    YANDEX = "yandex"


class Settings(BaseSettings):
    """Настройки приложения."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # GitHub Configuration
    github_token: str
    github_app_id: Optional[str] = None
    github_app_private_key: Optional[str] = None
    github_app_installation_id: Optional[str] = None

    # LLM Configuration
    llm_provider: LLMProvider = LLMProvider.OPENAI
    openai_api_key: Optional[str] = None
    yandex_api_key: Optional[str] = None
    yandex_folder_id: Optional[str] = None

    # Agent Configuration
    max_iterations: int = 5
    code_agent_timeout: int = 300  # seconds
    reviewer_timeout: int = 180  # seconds
    max_diff_tokens: int = 8000

    # Webhook Configuration
    webhook_secret: Optional[str] = None
    webhook_port: int = 8000

    # Logging
    log_level: str = "INFO"

    def get_llm_api_key(self) -> str:
        """Получить API ключ для выбранного провайдера."""
        if self.llm_provider == LLMProvider.OPENAI:
            if not self.openai_api_key:
                raise ValueError("OPENAI_API_KEY не установлен")
            return self.openai_api_key
        elif self.llm_provider == LLMProvider.YANDEX:
            if not self.yandex_api_key:
                raise ValueError("YANDEX_API_KEY не установлен")
            return self.yandex_api_key
        else:
            raise ValueError(f"Неподдерживаемый провайдер: {self.llm_provider}")

    def get_github_token(self) -> str:
        """Получить токен GitHub."""
        if not self.github_token:
            raise ValueError("GITHUB_TOKEN не установлен")
        return self.github_token


# Глобальный экземпляр настроек
settings = Settings()
