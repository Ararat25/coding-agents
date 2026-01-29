"""Тесты для конфигурации."""

import os
from unittest.mock import patch

import pytest

from coding_agents.config import Settings, LLMProvider


def test_settings_defaults():
    """Тест значений по умолчанию."""
    with patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"}):
        settings = Settings()
        assert settings.max_iterations == 5
        assert settings.code_agent_timeout == 300
        assert settings.reviewer_timeout == 180
        assert settings.llm_provider == LLMProvider.OPENAI


def test_get_llm_api_key_openai():
    """Тест получения OpenAI API ключа."""
    with patch.dict(
        os.environ,
        {
            "GITHUB_TOKEN": "test_token",
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "test_openai_key",
        },
    ):
        settings = Settings()
        assert settings.get_llm_api_key() == "test_openai_key"


def test_get_llm_api_key_yandex():
    """Тест получения Yandex API ключа."""
    with patch.dict(
        os.environ,
        {
            "GITHUB_TOKEN": "test_token",
            "LLM_PROVIDER": "yandex",
            "YANDEX_API_KEY": "test_yandex_key",
        },
    ):
        settings = Settings()
        assert settings.get_llm_api_key() == "test_yandex_key"
