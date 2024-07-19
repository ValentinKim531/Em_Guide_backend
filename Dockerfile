FROM python:3.10.2

WORKDIR /app

# Обновление и установка ffmpeg, libasound2-dev и других необходимых пакетов
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y redis-server libasound2-dev ffmpeg

# Копируем и устанавливаем зависимости
COPY requirements.txt .
RUN python -m venv /app/venv && \
    /app/venv/bin/pip install --upgrade pip && \
    /app/venv/bin/pip install -r requirements.txt

# Копируем весь проект
COPY . .

# Запуск Redis и приложения
CMD service redis-server start && /app/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
