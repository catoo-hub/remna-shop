#!/bin/bash

# Скрипт для обновления Remna Shop Bot

echo "🔄 Updating Remna Shop Bot"
echo "=========================="

# Переходим в директорию проекта
cd /opt/remna-shop

# Создаем бэкап текущей версии
echo "💾 Создаем бэкап текущей версии..."
BACKUP_DIR="/opt/remna-shop/backups/update-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Бэкапим важные файлы
cp .env "$BACKUP_DIR/"
cp -r data "$BACKUP_DIR/"
cp -r logs "$BACKUP_DIR/"

echo "✅ Бэкап создан в $BACKUP_DIR"

# Останавливаем бота
echo "⏹️  Останавливаем бота..."
systemctl stop remna-shop-bot

# Получаем обновления
echo "📥 Получаем обновления из репозитория..."
git stash  # Сохраняем локальные изменения
git pull origin main

if [ $? -ne 0 ]; then
    echo "❌ Ошибка при получении обновлений"
    echo "🔄 Восстанавливаем из бэкапа..."
    git stash pop
    systemctl start remna-shop-bot
    exit 1
fi

# Восстанавливаем .env если он был изменен
if [ -f "$BACKUP_DIR/.env" ]; then
    cp "$BACKUP_DIR/.env" .env
fi

# Проверяем изменения в requirements.txt
if git diff HEAD~1 requirements.txt > /dev/null; then
    echo "📦 Обнаружены изменения в зависимостях, пересобираем образ..."
    docker compose build --no-cache
else
    echo "🏗️  Пересобираем образ..."
    docker compose build
fi

# Запускаем обновленную версию
echo "🚀 Запускаем обновленную версию..."
systemctl start remna-shop-bot

# Ждем 10 секунд для инициализации
echo "⏳ Ждем инициализации..."
sleep 10

# Проверяем статус
if systemctl is-active --quiet remna-shop-bot; then
    echo "✅ Обновление успешно завершено!"
    echo "📊 Статус: systemctl status remna-shop-bot"
    echo "📝 Логи: journalctl -u remna-shop-bot -f"
else
    echo "❌ Ошибка при запуске обновленной версии"
    echo "🔄 Восстанавливаем предыдущую версию..."
    
    # Восстанавливаем из бэкапа
    git reset --hard HEAD~1
    cp "$BACKUP_DIR/.env" .env
    docker compose build
    systemctl start remna-shop-bot
    
    echo "⚠️  Откат выполнен. Проверьте логи для диагностики проблемы."
    exit 1
fi

echo ""
echo "🎉 Бот успешно обновлен!"
echo "📁 Бэкап сохранен в: $BACKUP_DIR"
