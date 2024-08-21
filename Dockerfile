# Используем официальный образ Python в качестве базового
FROM python:3.10.2

# Устанавливаем рабочую директорию
WORKDIR /app

# Обновление и установка зависимостей для FFmpeg
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y \
    autoconf \
    automake \
    build-essential \
    cmake \
    git-core \
    libass-dev \
    libfreetype6-dev \
    libgnutls28-dev \
    libmp3lame-dev \
    libopus-dev \
    libsdl2-dev \
    libtheora-dev \
    libtool \
    libva-dev \
    libvdpau-dev \
    libvorbis-dev \
    libxcb1-dev \
    libxcb-shm0-dev \
    libxcb-xfixes0-dev \
    pkg-config \
    texinfo \
    wget \
    yasm \
    zlib1g-dev \
    libx264-dev \
    libx265-dev \
    libnuma-dev \
    libvpx-dev \
    libasound2-dev \
    ffmpeg

# Копируем и устанавливаем зависимости
COPY requirements.txt .
RUN python -m venv /app/venv && \
    /app/venv/bin/pip install --upgrade pip && \
    /app/venv/bin/pip install -r requirements.txt
RUN apt-get update && apt-get install -y redis-server
# Копируем весь проект
COPY . .

# Открываем порты для FastAPI и WebSocket сервера
EXPOSE 8000

# Запуск Redis и приложения
CMD redis-server --daemonize yes && /app/venv/bin/python main.py

