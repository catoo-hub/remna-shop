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
from shop_bot.bot import handlers
from shop_bot.webhook_server.app import create_webhook_app
from shop_bot.config import PLANS
from shop_bot.data_manager.scheduler import start_subscription_monitor
from shop_bot.data_manager import database

def main():
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - [%(levelname)s] - %(name)s - (%(filename)s).%(funcName)s(%(lineno)d) - %(message)s"
    )
    logger = logging.getLogger(__name__)

    database.initialize_db()

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
        logger.info("Telegram Stars payment method is ENABLED.")
    else:
        logger.warning("Telegram Stars payment method is DISABLED.")

    if payment_methods["yookassa"]:
        Configuration.account_id = yookassa_shop_id
        Configuration.secret_key = yookassa_secret_key
        logger.info("YooKassa payment method is ENABLED.")
    else:
        logger.warning("YooKassa payment method is DISABLED (YOOKASSA_SHOP_ID or YOOKASSA_SECRET_KEY is missing in .env).")

    if payment_methods["crypto"]:
        logger.info("Crypto payment method is ENABLED.")
    else:
        logger.warning("Crypto payment method is DISABLED (CRYPTO_API_KEY is missing in .env).")

    if payment_methods["crypto_bot"]:
        logger.info("Crypto bot payment method is ENABLED.")
    else:
        logger.warning("Crypto bot payment method is DISABLED (CRYPTO_BOT_API is missing in .env).")

    if not any(payment_methods.values()):
        logger.critical("!!! NO PAYMENT SYSTEMS CONFIGURED! Bot cannot accept payments. !!!")
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
        logger.info("Flask server started on port 1488.")

        if database.get_all_vpn_users():
            asyncio.create_task(start_subscription_monitor(bot))

        logger.info("Aiogram Bot polling started...")
        await dp.start_polling(bot)

    try:
        asyncio.run(start_all())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")

if __name__ == "__main__":
    main()