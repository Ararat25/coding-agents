"""Клиенты для работы с LLM."""

import json
import logging
from typing import Optional

from openai import OpenAI

from coding_agents.config import LLMProvider, settings
from coding_agents.domain.interfaces import LLMClientInterface

logger = logging.getLogger(__name__)


class OpenAIClient(LLMClientInterface):
    """Клиент для OpenAI API."""

    def __init__(self, api_key: Optional[str] = None):
        """Инициализация клиента."""
        self.api_key = api_key or settings.get_llm_api_key()
        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4o-mini"

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
    ) -> str:
        """Сгенерировать ответ от LLM."""
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens or 4000,
                temperature=temperature,
            )

            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Ошибка при генерации ответа OpenAI: {e}")
            raise

    def generate_structured(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_format: Optional[dict] = None,
    ) -> dict:
        """Сгенерировать структурированный ответ (JSON)."""
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            # Добавляем инструкцию по формату JSON
            json_instruction = "\n\nОтветь ТОЛЬКО валидным JSON без дополнительного текста."
            if response_format:
                json_instruction += f"\nФормат: {json.dumps(response_format, ensure_ascii=False, indent=2)}"
            prompt_with_format = prompt + json_instruction

            messages.append({"role": "user", "content": prompt_with_format})

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.3,  # Низкая температура для более детерминированного JSON
            )

            content = response.choices[0].message.content
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON ответа: {e}")
            # Пытаемся извлечь JSON из текста
            try:
                # Ищем JSON в тексте
                start = content.find("{")
                end = content.rfind("}") + 1
                if start >= 0 and end > start:
                    return json.loads(content[start:end])
            except:
                pass
            raise
        except Exception as e:
            logger.error(f"Ошибка при генерации структурированного ответа OpenAI: {e}")
            raise


class YandexGPTClient(LLMClientInterface):
    """Клиент для YandexGPT API."""

    def __init__(self, api_key: Optional[str] = None, folder_id: Optional[str] = None):
        """Инициализация клиента."""
        self.api_key = api_key or settings.get_llm_api_key()
        self.folder_id = folder_id or settings.yandex_folder_id
        if not self.folder_id:
            raise ValueError("YANDEX_FOLDER_ID должен быть установлен")

        # Используем HTTP API YandexGPT
        self.model = "yandexgpt-lite"

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
    ) -> str:
        """Сгенерировать ответ от LLM."""
        try:
            # Используем HTTP API YandexGPT
            import httpx

            url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
            headers = {
                "Authorization": f"Api-Key {self.api_key}",
                "x-folder-id": self.folder_id,
            }

            messages = []
            if system_prompt:
                messages.append({"role": "system", "text": system_prompt})
            messages.append({"role": "user", "text": prompt})

            payload = {
                "modelUri": f"gpt://{self.folder_id}/{self.model}",
                "completionOptions": {
                    "stream": False,
                    "temperature": temperature,
                    "maxTokens": str(max_tokens or 4000),
                },
                "messages": messages,
            }

            with httpx.Client() as client:
                response = client.post(url, json=payload, headers=headers, timeout=60)
                response.raise_for_status()
                result = response.json()

            return result["result"]["alternatives"][0]["message"]["text"]
        except Exception as e:
            logger.error(f"Ошибка при генерации ответа YandexGPT: {e}")
            raise

    def generate_structured(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_format: Optional[dict] = None,
    ) -> dict:
        """Сгенерировать структурированный ответ (JSON)."""
        try:
            # Добавляем инструкцию по формату JSON
            json_instruction = "\n\nОтветь ТОЛЬКО валидным JSON без дополнительного текста."
            if response_format:
                json_instruction += f"\nФормат: {json.dumps(response_format, ensure_ascii=False, indent=2)}"
            prompt_with_format = prompt + json_instruction

            content = self.generate(
                prompt=prompt_with_format,
                system_prompt=system_prompt,
                temperature=0.3,
            )

            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON ответа YandexGPT: {e}")
            # Пытаемся извлечь JSON из текста
            try:
                start = content.find("{")
                end = content.rfind("}") + 1
                if start >= 0 and end > start:
                    return json.loads(content[start:end])
            except:
                pass
            raise
        except Exception as e:
            logger.error(f"Ошибка при генерации структурированного ответа YandexGPT: {e}")
            raise


def create_llm_client(provider: Optional[LLMProvider] = None) -> LLMClientInterface:
    """Фабрика для создания LLM клиента."""
    provider = provider or settings.llm_provider

    if provider == LLMProvider.OPENAI:
        return OpenAIClient()
    elif provider == LLMProvider.YANDEX:
        return YandexGPTClient()
    else:
        raise ValueError(f"Неподдерживаемый провайдер: {provider}")
