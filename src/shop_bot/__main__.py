import logging
import os
import threading
import asyncio
from dotenv import load_dotenv

from yookassa import Configuration
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode 

from shop_bot.bot import handlers
from shop_bot.bot import admin_handlers
from shop_bot.webhook_server.app import create_webhook_app
from shop_bot.data_manager.scheduler import start_subscription_monitor
from shop_bot.utils.logger import bot_logger
from shop_bot.config import PLANS
from shop_bot.data_manager import database

def main():
    load_dotenv()
    
    # Отключаем стандартные логи для чистоты
    logging.getLogger('aiogram').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    
    bot_logger.startup("Initializing Remna Shop Bot...")

    database.initialize_db()
    bot_logger.system("DATABASE", "SQLite database initialized", "OK")

    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME")
    ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")

    yookassa_shop_id = os.getenv("YOOKASSA_SHOP_ID")
    yookassa_secret_key = os.getenv("YOOKASSA_SECRET_KEY")
    crypto_api_key = os.getenv("CRYPTO_API_KEY")
    crypto_merchant_id = os.getenv("CRYPTO_MERCHANT_ID")
    crypto_bot_api = os.getenv("CRYPTO_BOT_API")

    yookassa_enabled = bool(yookassa_shop_id and yookassa_shop_id.strip() and yookassa_secret_key and yookassa_secret_key.strip())
    crypto_enabled = bool(crypto_api_key and crypto_api_key.strip() and crypto_merchant_id and crypto_merchant_id.strip())
    crypto_bot_enabled = bool(crypto_bot_api and crypto_bot_api.strip())
    stars_enabled = bool(os.getenv("STARS_ENABLED", "true").lower() == "true")  # По умолчанию включен

    if not TELEGRAM_TOKEN or not TELEGRAM_BOT_USERNAME:
        raise ValueError("Необходимо установить TELEGRAM_BOT_TOKEN и TELEGRAM_BOT_USERNAME")

    payment_methods = {
        "stars": stars_enabled,
        "yookassa": yookassa_enabled,
        "crypto": crypto_enabled,
        "crypto_bot": crypto_bot_enabled
    }

    if payment_methods["stars"]:
        bot_logger.system("PAYMENTS", "Telegram Stars payment enabled", "OK")
    else:
        bot_logger.system("PAYMENTS", "Telegram Stars payment disabled", "WARNING")

    if payment_methods["yookassa"]:
        Configuration.account_id = yookassa_shop_id
        Configuration.secret_key = yookassa_secret_key
        bot_logger.system("PAYMENTS", "YooKassa payment enabled", "OK")
    else:
        bot_logger.system("PAYMENTS", "YooKassa payment disabled (credentials missing)", "WARNING")

    if payment_methods["crypto"]:
        bot_logger.system("PAYMENTS", "Crypto payment enabled", "OK")
    else:
        bot_logger.system("PAYMENTS", "Crypto payment disabled (API key missing)", "WARNING")

    if payment_methods["crypto_bot"]:
        bot_logger.system("PAYMENTS", "Crypto bot payment enabled", "OK")
    else:
        bot_logger.system("PAYMENTS", "Crypto bot payment disabled (API missing)", "WARNING")

    if not any(payment_methods.values()):
        bot_logger.system("PAYMENTS", "NO PAYMENT SYSTEMS CONFIGURED!", "ERROR")
        bot_logger.critical("Bot cannot accept payments - shutting down")
        return
    
    handlers.PLANS = PLANS
    handlers.TELEGRAM_BOT_USERNAME = TELEGRAM_BOT_USERNAME
    handlers.CRYPTO_API_KEY = crypto_api_key
    handlers.CRYPTO_MERCHANT_ID = crypto_merchant_id
    handlers.PAYMENT_METHODS = payment_methods
    handlers.ADMIN_TELEGRAM_ID = ADMIN_TELEGRAM_ID
    
    bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(admin_handlers.admin_router)
    dp.include_router(handlers.user_router)

    flask_app = create_webhook_app(bot, handlers.process_successful_payment)

    async def start_all():
        loop = asyncio.get_running_loop()
        flask_app.config['EVENT_LOOP'] = loop

        flask_thread = threading.Thread(
            target=lambda: flask_app.run(host='0.0.0.0', port=1488, use_reloader=False),
            daemon=True
        )
        flask_thread.start()
        bot_logger.system("WEBHOOK", "Flask server started on port 1488", "OK")

        if database.get_all_vpn_users():
            asyncio.create_task(start_subscription_monitor(bot))

        bot_logger.system("TELEGRAM", "Bot polling started", "OK")
        await dp.start_polling(bot)

    try:
        asyncio.run(start_all())
    except (KeyboardInterrupt, SystemExit):
        bot_logger.shutdown()
        bot_logger.info("Bot stopped gracefully")

if __name__ == "__main__":
    main()