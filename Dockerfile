# Используем официальный образ Python в качестве базового
FROM python:3.10.2

# Устанавливаем рабочую директорию
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

# Открываем порты для FastAPI и WebSocket сервера
EXPOSE 8000

# Запуск Redis и приложения
CMD service redis-server start && /app/venv/bin/python main.py
