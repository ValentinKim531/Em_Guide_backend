# Используем официальный образ Python в качестве базового
FROM python:3.10.2

# Устанавливаем рабочую директорию
WORKDIR /app

# Обновление и установка зависимостей для сборки FFmpeg
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
    libfdk-aac-dev \
    libx264-dev \
    libx265-dev \
    libnuma-dev \
    libvpx-dev \
    libasound2-dev

# Клонирование и сборка FFmpeg с нужными опциями
RUN git clone --depth 1 https://git.ffmpeg.org/ffmpeg.git ffmpeg && \
    cd ffmpeg && \
    ./configure \
      --enable-gpl \
      --enable-libass \
      --enable-libfdk-aac \
      --enable-libfreetype \
      --enable-libmp3lame \
      --enable-libopus \
      --enable-libvorbis \
      --enable-libvpx \
      --enable-libx264 \
      --enable-libx265 \
      --enable-nonfree && \
    make -j$(nproc) && \
    make install && \
    make distclean && \
    hash -r

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
