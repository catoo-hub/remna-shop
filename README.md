# 🚀 Remna Shop Bot

Современный Telegram бот для продажи VPN услуг с интеграцией Remnawave панели и красивой системой логирования.

## ⭐ Возможности

- 💳 **Многоплатформенные платежи**: Telegram Stars, YooKassa, Crypto
- 🔐 **VPN управление**: Автоматическое создание и управление VLESS Reality конфигурациями
- 👥 **Реферальная система**: Бонусы за привлечение новых пользователей
- 📊 **Админ панель**: Детальная статистика и управление
- 💾 **Система бэкапов**: Автоматическое резервное копирование каждые 6 часов
- 📝 **Красивые логи**: Цветное логирование в стиле современных фреймворков
- 🐳 **Docker поддержка**: Готовое развертывание в контейнерах
- 🔄 **Автообновления**: Простая система обновлений

## 🚀 Быстрый старт

### Автоматическое развертывание

**Linux:**

```bash
git clone <your-repo-url> /opt/remna-shop
cd /opt/remna-shop
chmod +x deploy.sh
sudo ./deploy.sh
```

**Windows:**

```powershell
git clone <your-repo-url> C:\remna-shop
cd C:\remna-shop
.\deploy.bat
```

### Ручная настройка

1. **Клонируйте репозиторий**

```bash
git clone <your-repo-url>
cd remna-shop
```

2. **Создайте .env файл**

```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_BOT_USERNAME=your_bot_username
ADMIN_TELEGRAM_ID=your_admin_id
REMNA_API_URL=https://your-panel.com
REMNA_API_USERNAME=your_username
REMNA_API_PASSWORD=your_password
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret_key
```

3. **Запустите с Docker**

```bash
docker compose up -d --build
```

## 📋 Системные требования

- **OS**: Linux (Ubuntu 20.04+) или Windows 10/11 Pro
- **RAM**: 2GB (минимум 1GB)
- **Storage**: 10GB свободного места
- **Software**: Docker, Docker Compose

## �️ Управление

### Основные команды

```bash
# Статус и логи
systemctl status remna-shop-bot
journalctl -u remna-shop-bot -f

# Docker команды
docker compose ps
docker compose logs -f
docker compose restart

# Мониторинг
./monitor.sh
./monitor.sh --watch

# Обновление
./update.sh
```

### Структура проекта

```
remna-shop/
├── src/shop_bot/              # Основной код бота
│   ├── bot/                   # Telegram bot handlers
│   ├── data_manager/          # База данных и планировщик
│   ├── modules/              # API модули
│   ├── utils/                # Утилиты (логгер)
│   └── webhook_server/       # Webhook сервер
├── data/                     # База данных SQLite
├── logs/                     # Файлы логов
├── backups/                  # Автоматические бэкапы
├── docker-compose.yml        # Docker конфигурация
├── Dockerfile               # Docker образ
├── deploy.sh               # Скрипт развертывания (Linux)
├── deploy.bat             # Скрипт развертывания (Windows)
├── update.sh             # Скрипт обновления
├── monitor.sh           # Скрипт мониторинга
└── DEPLOYMENT.md       # Подробная инструкция
```

## 🎨 Особенности логирования

Бот использует современную систему логирования с цветовой индикацией:

```
🚀 [STARTUP] Bot initialization started
💳 [PAYMENT] Payment processed: 100.00 RUB
👤 [USER] New user registered: @username
🔐 [VPN] Configuration created for user
💾 [BACKUP] Database backup completed
🌐 [API] API request to Remnawave successful
📨 [NOTIFICATION] Message sent to admin
⚙️ [SYSTEM] Health check completed
```

## 📊 Мониторинг

Встроенная система мониторинга отслеживает:

- ✅ Статус сервисов и Docker контейнеров
- 📊 Использование ресурсов (CPU, RAM)
- 🔍 Анализ логов на ошибки
- 💽 Использование дискового пространства
- 🌐 Доступность API
- 💾 Состояние бэкапов
- 📈 Статистика активности

## 🔒 Безопасность

- 🔐 Все API ключи в переменных окружения
- 🛡️ Защита от несанкционированного доступа
- 📱 Telegram webhook с SSL сертификатом
- 💾 Автоматическое резервное копирование
- 🔄 Система автообновлений с откатом

## 🆘 Поддержка

### Частые проблемы

**Бот не отвечает:**

```bash
docker-compose logs -f
systemctl status remna-shop-bot
```

**Ошибки платежей:**

```bash
tail -f logs/payments.log
```

**Проблемы с API:**

```bash
curl -k https://your-panel.com/api/health
tail -f logs/api.log
```

### Полезные команды

```bash
# Перезапуск с пересборкой
docker compose up -d --build

# Очистка Docker
docker system prune -f

# Просмотр использования ресурсов
docker stats

# Ротация логов
find logs/ -name "*.log" -size +100M -delete
```

## 📈 Обновления

Автоматическое обновление с сохранением данных:

```bash
./update.sh
```

Скрипт автоматически:

- 💾 Создает бэкап текущей версии
- 📥 Загружает обновления из репозитория
- 🏗️ Пересобирает Docker образ
- 🚀 Запускает обновленную версию
- 🔄 Откатывается при ошибках

## 📄 Документация

- 📖 [Подробная инструкция по развертыванию](DEPLOYMENT.md)
- 🔧 [Конфигурация и настройка](docs/configuration.md)
- 🔌 [API документация](docs/api.md)
- 🐛 [Troubleshooting](docs/troubleshooting.md)
  Откройте файл .env.example для редактирования:

```bash
nano .env.example
```

Заполните все необходимые поля, следуя примерам в файле. Сохраните и закройте файл (Ctrl + X, затем Y и Enter).

3. Создайте основной файл конфигурации:

```bash
cp .env.example .env
```

## ⚙️ Настройка Nginx для вебхуков YooKassa

Вебхуки — это способ, которым YooKassa уведомляет вашего бота о статусе платежей. Чтобы эти уведомления доходили до бота, необходимо настроить ваш веб-сервер Nginx в качестве обратного прокси (reverse proxy).

### ❗️ Важно: YooKassa может отправлять вебхуки только на порты 443 или 8443. Убедитесь, что вы используете один из них в вашей конфигурации.

Шаг 1: Создайте файл конфигурации

Создайте новый файл конфигурации для бота в директории Nginx.

```bash
sudo nano /etc/nginx/sites-enabled/remna-shop.conf
```

Шаг 2: Добавьте конфигурацию

Вставьте в этот файл следующий код, заменив значения-заполнители (<... >) на свои.

```nginx
server {
    # ВАЖНО: Используйте порт 443 или 8443. Другие порты для YooKassa не работают!
    listen 8443 ssl http2;
    listen [::]:8443 ssl http2; # Для IPv6

    # ЗАМЕНИТЕ НА ВАШ ДОМЕН
    server_name <your_domain.com>;

    # --- Настройки SSL ---
    # Укажите правильные пути к вашим SSL-сертификатам
    ssl_certificate /etc/letsencrypt/live/<your_domain.com>/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/<your_domain.com>/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305';

    # --- Маршрутизация для вебхуков YooKassa ---
    # Этот блок говорит Nginx, что все запросы на /yookassa-webhook
    # нужно перенаправлять боту.
    location /yookassa-webhook {
        proxy_pass http://127.0.0.1:1488;

        # Стандартные заголовки для корректной работы вебхуков
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Шаг 3: Проверьте и примените конфигурацию

Проверьте Nginx на синтаксические ошибки:

```bash
sudo nginx -t
```

Если видите test is successful, все в порядке.

Перезагрузите Nginx, чтобы применить изменения:

```bash
sudo systemctl reload nginx
```

Не забудьте открыть порт в файрволе (если он используется):

```bash
# Если используете порт 8443
sudo ufw allow 8443/tcp

# Если используете порт 443
sudo ufw allow 443/tcp
```

Запустите бота:

```bash
docker compose up -d
```

## 🤖 Настройка в админ-панели

После запуска бота зайдите в админ-панель и настройте следующие параметры:

Текст "О проекте"

Условия пользования (необязательно)

Политика конфиденциальности (необязательно)

Ссылка на поддержку (например, https://t.me/username)

Текст поддержки (необязательно)

## 💳 Настройка YooKassa / СБП

Для приема платежей получите официальный токен от YooKassa.

В личном кабинете YooKassa укажите URL для вебхуков. Помните, что URL должен указывать на порт 443 или 8443.

Пример для порта 8443: https://my-vpn-shop.com:8443/yookassa-webhook

Пример для порта 443: https://my-vpn-shop.com/yookassa-webhook (порт 443 является стандартным для HTTPS и его можно не указывать).

## 💡 Важная информация

Тестовый период: В боте реализована система 3-дневного тестового периода.

Обратная связь: Если у вас есть пожелания или вы нашли баг, создайте ["Issue"](https://github.com/catoo-hub/remna-shop/issues) в репозитории GitHub или напишите в [Telegram](https://t.me/torroixq).
