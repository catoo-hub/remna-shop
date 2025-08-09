# Используем официальный Python образ
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Создаем директорию для базы данных и логов
RUN mkdir -p /app/data /app/logs

# Устанавливаем переменные окружения
ENV PYTHONPATH=/app:/app/src
ENV PYTHONUNBUFFERED=1

# Открываем порт для веб-хуков
EXPOSE 1488

# Запускаем бота
CMD ["python", "-m", "src.shop_bot"]