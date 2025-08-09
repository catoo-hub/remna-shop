@echo off
REM Скрипт для развертывания Remna Shop Bot на Windows

echo 🚀 Deploying Remna Shop Bot to Production (Windows)
echo =========================================

REM Проверяем Docker Desktop
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker не найден. Пожалуйста, установите Docker Desktop для Windows
    echo https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

REM Проверяем Docker Compose
docker compose version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker Compose не найден. Убедитесь, что Docker Desktop включает Compose
    pause
    exit /b 1
)

echo ✅ Docker найден

REM Создаем директории для данных
echo 📁 Создаем директории для данных...
if not exist "data" mkdir data
if not exist "logs" mkdir logs
if not exist "backups" mkdir backups

REM Проверяем .env файл
if not exist ".env" (
    echo ⚠️  .env файл не найден. Создаем шаблон...
    (
        echo # Telegram Bot Configuration
        echo TELEGRAM_BOT_TOKEN=your_bot_token_here
        echo TELEGRAM_BOT_USERNAME=your_bot_username_here
        echo ADMIN_TELEGRAM_ID=your_admin_id_here
        echo.
        echo # YooKassa Payment System
        echo YOOKASSA_SHOP_ID=your_yookassa_shop_id
        echo YOOKASSA_SECRET_KEY=your_yookassa_secret_key
        echo.
        echo # Crypto Payment Systems
        echo CRYPTO_API_KEY=your_crypto_api_key
        echo CRYPTO_MERCHANT_ID=your_crypto_merchant_id
        echo CRYPTO_BOT_API=your_crypto_bot_api
        echo CRYPTO_WEBHOOK_URL=https://yourdomain.com/crypto_webhook
        echo.
        echo # Telegram Stars
        echo STARS_RATE=2.0
        echo.
        echo # Remnawave API
        echo REMNA_API_URL=https://your-remnawave-panel.com
        echo REMNA_API_USERNAME=your_api_username
        echo REMNA_API_PASSWORD=your_api_password
        echo REMNA_FLOW=xtls-rprx-vision
    ) > .env
    
    echo ❗ Пожалуйста, отредактируйте файл .env с вашими настройками
    echo После настройки запустите deploy.bat снова
    notepad .env
    pause
    exit /b 1
)

REM Собираем образ
echo 🏗️  Собираем Docker образ...
docker compose build

if %errorlevel% neq 0 (
    echo ❌ Ошибка при сборке образа
    pause
    exit /b 1
)

REM Запускаем контейнер
echo 🚀 Запускаем бота...
docker compose up -d

if %errorlevel% neq 0 (
    echo ❌ Ошибка при запуске
    pause
    exit /b 1
)

echo.
echo ✅ Развертывание завершено!
echo.
echo 📊 Управление ботом:
echo    Статус:    docker compose ps
echo    Логи:      docker compose logs -f
echo    Остановка: docker compose down
echo    Рестарт:   docker compose restart
echo.
echo 📁 Директории:
echo    База:      .\data
echo    Логи:      .\logs
echo    Бэкапы:    .\backups
echo.
echo 🌐 Для просмотра логов запустите: docker compose logs -f
pause
