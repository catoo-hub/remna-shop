#!/bin/bash

# Скрипт для развертывания Remna Shop Bot в продакшен

echo "🚀 Deploying Remna Shop Bot to Production"
echo "========================================"

# Проверяем, что Docker установлен
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не найден. Устанавливаем Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    sudo usermod -aG docker $USER
    echo "✅ Docker установлен"
fi

# Проверяем, что Docker Compose установлен
if ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose не найден. Проверьте установку Docker Desktop..."
    echo "Docker Compose входит в состав современного Docker"
    exit 1
fi
echo "✅ Docker Compose найден"

# Создаем директории
echo "📁 Создаем необходимые директории..."
mkdir -p /opt/remna-shop
mkdir -p /opt/remna-shop/data
mkdir -p /opt/remna-shop/logs
mkdir -p /opt/remna-shop/backups

# Копируем файлы (предполагаем, что скрипт запускается из директории проекта)
echo "📋 Копируем файлы проекта..."
cp -r . /opt/remna-shop/
cd /opt/remna-shop

# Проверяем наличие .env файла
if [ ! -f ".env" ]; then
    echo "⚠️  .env файл не найден. Создаем шаблон..."
    cat > .env << EOF
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_BOT_USERNAME=your_bot_username_here
ADMIN_TELEGRAM_ID=your_admin_id_here

# YooKassa Payment System
YOOKASSA_SHOP_ID=your_yookassa_shop_id
YOOKASSA_SECRET_KEY=your_yookassa_secret_key

# Crypto Payment Systems
CRYPTO_API_KEY=your_crypto_api_key
CRYPTO_MERCHANT_ID=your_crypto_merchant_id
CRYPTO_BOT_API=your_crypto_bot_api
CRYPTO_WEBHOOK_URL=https://yourdomain.com/crypto_webhook

# Telegram Stars
STARS_RATE=2.0

# Remnawave API
REMNA_API_URL=https://your-remnawave-panel.com
REMNA_API_USERNAME=your_api_username
REMNA_API_PASSWORD=your_api_password
REMNA_FLOW=xtls-rprx-vision
EOF
    echo "❗ Пожалуйста, отредактируйте файл .env с вашими настройками:"
    echo "   nano /opt/remna-shop/.env"
    echo ""
    echo "После настройки .env запустите:"
    echo "   systemctl start remna-shop-bot"
    exit 1
fi

# Устанавливаем systemd service
echo "⚙️  Настраиваем systemd service..."
sudo cp remna-shop-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable remna-shop-bot

# Собираем и запускаем контейнер
echo "🏗️  Собираем Docker образ..."
docker compose build

echo "🚀 Запускаем бота..."
sudo systemctl start remna-shop-bot

echo ""
echo "✅ Развертывание завершено!"
echo ""
echo "📊 Управление ботом:"
echo "   Статус:    systemctl status remna-shop-bot"
echo "   Логи:      journalctl -u remna-shop-bot -f"
echo "   Остановка: systemctl stop remna-shop-bot"
echo "   Запуск:    systemctl start remna-shop-bot"
echo "   Рестарт:   systemctl restart remna-shop-bot"
echo ""
echo "🔍 Docker команды:"
echo "   Логи:      docker compose logs -f"
echo "   Состояние: docker compose ps"
echo "   Рестарт:   docker compose restart"
echo ""
echo "📁 Директории:"
echo "   Проект:    /opt/remna-shop"
echo "   База:      /opt/remna-shop/data"
echo "   Логи:      /opt/remna-shop/logs"
echo "   Бэкапы:    /opt/remna-shop/backups"
