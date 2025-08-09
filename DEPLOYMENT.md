# 🚀 Развертывание Remna Shop Bot в продакшен

## Подготовка к развертыванию

### 1. Системные требования

**Linux (Ubuntu/Debian):**

- Ubuntu 20.04+ или Debian 11+
- 2GB RAM (минимум 1GB)
- 10GB свободного места
- Docker и Docker Compose

**Windows:**

- Windows 10/11 Pro
- Docker Desktop
- PowerShell или CMD

### 2. Подготовка окружения

#### Linux

```bash
# Обновляем систему
sudo apt update && sudo apt upgrade -y

# Устанавливаем необходимые пакеты
sudo apt install -y curl wget git

# Клонируем репозиторий
git clone <your-repo-url> /opt/remna-shop
cd /opt/remna-shop

# Делаем скрипт исполняемым
chmod +x deploy.sh

# Запускаем развертывание
sudo ./deploy.sh
```

#### Windows

```powershell
# Клонируем репозиторий
git clone <your-repo-url> C:\remna-shop
cd C:\remna-shop

# Запускаем развертывание
.\deploy.bat
```

## Настройка конфигурации

### 1. Файл .env

После первого запуска скрипта будет создан файл `.env` с шаблоном настроек:

```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=1234567890:AAAA-BBBB-CCCC-DDDD
TELEGRAM_BOT_USERNAME=your_bot_username
ADMIN_TELEGRAM_ID=123456789

# YooKassa Payment System
YOOKASSA_SHOP_ID=123456
YOOKASSA_SECRET_KEY=test_ABCDEF...

# Crypto Payment Systems
CRYPTO_API_KEY=your_crypto_api_key
CRYPTO_MERCHANT_ID=your_merchant_id
CRYPTO_BOT_API=your_crypto_bot_api
CRYPTO_WEBHOOK_URL=https://yourdomain.com/crypto_webhook

# Telegram Stars
STARS_RATE=2.0

# Remnawave API
REMNA_API_URL=https://your-panel.com
REMNA_API_USERNAME=admin
REMNA_API_PASSWORD=your_password
REMNA_FLOW=xtls-rprx-vision
```

### 2. Получение токена бота

1. Перейдите к [@BotFather](https://t.me/BotFather) в Telegram
2. Создайте нового бота командой `/newbot`
3. Введите имя и username бота
4. Сохраните полученный токен в `.env`

### 3. Настройка YooKassa

1. Зарегистрируйтесь на [yookassa.ru](https://yookassa.ru)
2. Получите Shop ID и Secret Key
3. Добавьте их в `.env`

## Управление ботом

### Linux (systemd)

```bash
# Статус бота
systemctl status remna-shop-bot

# Просмотр логов
journalctl -u remna-shop-bot -f

# Остановка
systemctl stop remna-shop-bot

# Запуск
systemctl start remna-shop-bot

# Рестарт
systemctl restart remna-shop-bot

# Отключение автозапуска
systemctl disable remna-shop-bot
```

### Docker команды (Linux/Windows)

```bash
# Статус контейнеров
docker-compose ps

# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down

# Запуск
docker-compose up -d

# Рестарт
docker-compose restart

# Пересборка и запуск
docker-compose up -d --build
```

## Мониторинг и обслуживание

### 1. Логи

Логи сохраняются в:

- Linux: `/opt/remna-shop/logs/`
- Windows: `.\logs\`

Структура логов:

```
logs/
├── bot.log          # Основные логи бота
├── payments.log     # Логи платежей
├── api.log         # Логи API запросов
└── backup.log      # Логи бэкапов
```

### 2. Бэкапы

Автоматические бэкапы создаются каждые 6 часов в:

- Linux: `/opt/remna-shop/backups/`
- Windows: `.\backups\`

Ручное создание бэкапа:

```bash
# Через Docker
docker-compose exec remna-shop-bot python -c "
from src.shop_bot.data_manager.database import DatabaseManager
db = DatabaseManager()
db.create_backup()
"
```

### 3. Обновление

```bash
# Остановка бота
docker-compose down

# Получение обновлений
git pull

# Пересборка и запуск
docker-compose up -d --build
```

## Безопасность

### 1. Firewall настройки

```bash
# Ubuntu/Debian
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (если используется webhook)
sudo ufw allow 443/tcp   # HTTPS (если используется webhook)
sudo ufw enable
```

### 2. SSL сертификат (для webhook)

Если используете webhook, настройте SSL:

```bash
# Установка Certbot
sudo apt install certbot

# Получение сертификата
sudo certbot certonly --standalone -d yourdomain.com

# Обновление docker-compose.yml для SSL
```

### 3. Резервные копии

Настройте регулярное резервное копирование:

```bash
# Добавить в crontab
0 3 * * * /opt/remna-shop/backup.sh
```

## Troubleshooting

### Частые проблемы

1. **Бот не отвечает**

   ```bash
   # Проверьте логи
   docker-compose logs -f

   # Проверьте токен
   grep TELEGRAM_BOT_TOKEN .env
   ```

2. **Ошибки платежей**

   ```bash
   # Проверьте настройки YooKassa
   grep YOOKASSA .env

   # Проверьте логи платежей
   tail -f logs/payments.log
   ```

3. **Проблемы с API**

   ```bash
   # Проверьте подключение к Remnawave
   curl -k https://your-panel.com/api/health

   # Проверьте логи API
   tail -f logs/api.log
   ```

### Полезные команды

```bash
# Просмотр использования ресурсов
docker stats

# Очистка Docker
docker system prune -f

# Проверка места на диске
df -h

# Просмотр активных процессов
htop
```

## Поддержка

При возникновении проблем:

1. Проверьте логи бота
2. Убедитесь в правильности настроек `.env`
3. Проверьте доступность API Remnawave
4. Создайте issue в репозитории проекта
