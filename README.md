Это Fork репозитория 3x-ui-shop от **evansvl**
[Ссылка на официальный репозиторий](https://github.com/evansvl/3x-ui-shop/)

# remna-shop | Telegram-бот для продажи VLESS-конфигов

![alt text](https://img.shields.io/badge/version-1.0.3-blue)
![alt text](https://img.shields.io/badge/language-Python-green)
![alt text](https://img.shields.io/github/issues/catoo-hub/remna-shop)

remna-shop — это Telegram-бот для автоматизированной продажи VLESS-конфигураций, который интегрируется с панелью управления remnawave. Бот предоставляет удобный интерфейс для пользователей и администраторов, а также автоматизирует процесс оплаты через YooKassa.

## 🚀 Основные возможности

Автоматическая продажа: Полностью автоматизированный процесс продажи VLESS-конфигов.

Интеграция с YooKassa: Прием платежей через популярную платежную систему YooKassa.

Админ-панель: Удобная панель для настройки информации о проекте, ссылок на условия пользования, политику конфиденциальности, поддержку и группу.

Тестовый период: Встроенная система 3-дневного тестового периода для новых пользователей.

## ⚠️ Требования

SSL-сертификат: Для корректной работы бота обязательно наличие SSL-сертификата для домена, который вы будете использовать.

Порты для YooKassa: YooKassa отправляет вебхуки только на порты 443 (стандартный для HTTPS) и 8443. Использование других портов для приема уведомлений от YooKassa невозможно.

## 🛠️ Установка

1. Клонируйте репозиторий:

```bash
git clone --branch Latest https://github.com/catoo-hub/remna-shop/
cd remna-shop
```

2. Настройте переменные окружения:
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
