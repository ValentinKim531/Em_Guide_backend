# Используем официальный образ Python в качестве базового
FROM python:3.10.2

# Устанавливаем рабочую директорию
WORKDIR /app

# Обновляем и устанавливаем необходимые пакеты
RUN apt-get update && \
    apt-get install -y \
    redis-server && \
    apt-get clean

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
CMD redis-server --daemonize yes && /app/venv/bin/python main.py
