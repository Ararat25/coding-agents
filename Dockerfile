FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Копирование файлов проекта
COPY pyproject.toml ./
COPY requirements.txt ./

# Установка зависимостей Python
RUN pip install -r requirements.txt && \
    pip install -e .

# Копирование исходного кода
COPY src/ ./src/
COPY . .

# Создание директории для репозиториев
RUN mkdir -p /app/repos

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

# Точка входа
CMD ["python", "-m", "coding_agents.api.server"]
