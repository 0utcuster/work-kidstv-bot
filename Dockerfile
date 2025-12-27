# Dockerfile
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Системные пакеты (минимум) + greenlet для SQLAlchemy async
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# Установим зависимости
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
 && pip install -r requirements.txt \
 && pip install greenlet

# Копируем код
COPY . /app

# Важно: база SQLite должна сохраняться между перезапусками
# Если у Вас bot.db в корне — будет храниться в volume.
VOLUME ["/app"]

CMD ["python", "-m", "app.main"]