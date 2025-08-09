import logging
import uuid
from io import BytesIO
from datetime import datetime, timedelta
import qrcode
from yookassa import Payment
import aiohttp
import os
import hashlib
import json
import tarfile
import shutil
from pathlib import Path

from aiogram import Bot, Router, F, types, html
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from shop_bot.bot import keyboards
from shop_bot.modules import remnawave_api
from shop_bot.data_manager.database import (
    get_user, add_new_key, get_user_keys, update_user_stats,
    register_user_if_not_exists, get_next_key_number, get_key_by_id,
    update_key_info, set_trial_used, reset_trial_used, set_terms_agreed, get_setting,
    get_promo, apply_promo_usage, ensure_user_ref_code, link_referral, count_referrals,
    set_auto_renew, get_auto_renew, log_action, has_action, add_traffic_extra,
    create_promo, get_all_promos
)
from shop_bot.config import (
    PLANS, get_profile_text, get_vpn_active_text, VPN_INACTIVE_TEXT, VPN_NO_DATA_TEXT,
    get_key_info_text, CHOOSE_PAYMENT_METHOD_MESSAGE, get_purchase_success_text, ABOUT_TEXT, TERMS_URL, PRIVACY_URL, SUPPORT_USER, SUPPORT_TEXT
)
from shop_bot.config import TRAFFIC_PACKS
from shop_bot.modules.remnawave_api import add_extra_traffic

TELEGRAM_BOT_USERNAME = None
CRYPTO_API_KEY = None
CRYPTO_MERCHANT_ID = None
PAYMENT_METHODS = None
PLANS = None
ADMIN_ID = os.getenv("ADMIN_TELEGRAM_ID")

logger = logging.getLogger(__name__)

# Импорт красивого логгера
from shop_bot.utils.logger import bot_logger

async def create_backup_and_send(bot: Bot, admin_id: str, is_auto: bool = False) -> bool:
    """Создает бэкап базы данных и отправляет админу.
    
    Args:
        bot: Экземпляр бота
        admin_id: ID админа для отправки
        is_auto: True если автоматический бэкап, False если ручной
        
    Returns:
        bool: True если бэкап создан успешно, False в случае ошибки
    """
    backup_type = "🤖 Automatic" if is_auto else "📦 Manual"
    logger.info(f"🎯 Starting {backup_type.lower()} backup process...")
    
    try:
        # Получаем путь к базе данных
        from shop_bot.data_manager.database import DB_FILE, set_last_backup_timestamp
        db_path = Path(DB_FILE)
        
        # Создаем папку для бэкапов
        backups_dir = db_path.parent / 'backups'
        backups_dir.mkdir(exist_ok=True)
        bot_logger.backup("CREATE_DIR", f"Backup directory: {backups_dir}")
        
        # Генерируем имя файла бэкапа
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_part_aa"
        
        # Создаем tar.gz архив
        backup_file = backups_dir / f"{backup_name}.tar.gz"
        bot_logger.backup("CREATE_ARCHIVE", f"Creating: {backup_file.name}")
        
        with tarfile.open(backup_file, "w:gz") as tar:
            tar.add(db_path, arcname=db_path.name)
        
        # Получаем информацию о файле
        file_size = backup_file.stat().st_size
        # Исправляем расчет размера - если меньше 1 МБ, показываем в КБ
        if file_size >= 1024 * 1024:
            file_size_str = f"{file_size / (1024 * 1024):.1f} MB"
        else:
            file_size_str = f"{file_size / 1024:.1f} KB"
        
        # Получаем реальный IP сервера
        server_ip = "45.144.53.239"  # Можно вынести в env переменную
        
        # Обновляем timestamp последнего бэкапа (используем UTC)
        set_last_backup_timestamp(datetime.utcnow().isoformat())
        bot_logger.backup("UPDATE_TIMESTAMP", "Last backup timestamp updated")
        
        # Создаем красивое сообщение как в Marzban
        backup_type_text = "🤖 Auto Backup" if is_auto else "📦 Manual Backup"
        backup_text = (
            f"💾 <b>Backup Information</b>\n\n"
            f"🔧 <b>Type:</b> <code>{backup_type_text}</code>\n"
            f"🌐 <b>Server IP:</b> <code>{server_ip}</code>\n"
            f"📁 <b>Backup File:</b> <code>{backup_name}.tar.gz</code>\n"
            f"📅 <b>Backup Time:</b> <code>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</code>\n"
            f"📊 <b>File Size:</b> <code>{file_size_str}</code>"
        )
        
        # Отправляем файл админу
        bot_logger.backup("SEND_TO_ADMIN", f"Sending backup ({file_size_str})")
        try:
            with open(backup_file, 'rb') as f:
                backup_document = BufferedInputFile(f.read(), filename=f"{backup_name}.tar.gz")
                
            await bot.send_document(
                chat_id=admin_id,
                document=backup_document,
                caption=backup_text
            )
            
            bot_logger.backup("SUCCESS", f"Backup sent: {backup_file.name} ({file_size_str})", "OK")
            return True
            
        except Exception as e:
            bot_logger.backup("SEND_FAILED", f"Failed to send: {e}", "ERROR")
            return False
        
    except Exception as e:
        bot_logger.backup("CRITICAL_ERROR", f"Backup creation failed: {e}", "ERROR")
        return False

admin_router = Router()
user_router = Router()

async def show_main_menu(message: types.Message, edit_message: bool = False):
    user_id = message.chat.id
    user_db_data = get_user(user_id)
    user_keys = get_user_keys(user_id)
    
    trial_available = not (user_db_data and user_db_data.get('trial_used'))
    is_admin = str(user_id) == ADMIN_ID

    text = "🏠 <b>Главное меню</b>\n\nВыберите действие:"
    auto_renew = get_auto_renew(user_id) if user_db_data else False
    keyboard = keyboards.create_main_menu_keyboard(user_keys, trial_available, is_admin, auto_renew=auto_renew)
    
    if edit_message:
        try:
            await message.edit_text(text, reply_markup=keyboard)
        except TelegramBadRequest:
            pass
    else:
        await message.answer(text, reply_markup=keyboard)

class UserAgreement(StatesGroup):
    waiting_for_agreement = State()

class PromoInput(StatesGroup):
    waiting_for_code = State()

class PromoCreate(StatesGroup):
    waiting_for_code = State()
    waiting_for_discount = State()
    waiting_for_days = State()
    waiting_for_limit = State()

@user_router.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.full_name
    # Referral parsing /start ref_<code>
    ref_code = None
    if message.text and ' ' in message.text:
        arg = message.text.split(' ',1)[1]
        if arg.startswith('ref_'):
            ref_code = arg[4:]
    register_user_if_not_exists(user_id, username)
    user_data = get_user(user_id)
    if ref_code and user_data and not user_data.get('referred_by'):
        if link_referral(ref_code, user_id):
            log_action(user_id, 'referral_linked', ref_code)

    if user_data and user_data.get('agreed_to_terms'):
        await message.answer(
            f"👋 Снова здравствуйте, {html.bold(message.from_user.full_name)}!",
            reply_markup=keyboards.main_reply_keyboard
        )
        await show_main_menu(message)
    else:
        terms_url = get_setting("terms_url")
        privacy_url = get_setting("privacy_url")
        if not terms_url or not privacy_url:
            await message.answer("❗️ Условия использования и политика конфиденциальности не установлены. Пожалуйста, обратитесь к администратору.")
            return
        agreement_text = (
            "<b>Добро пожаловать!</b>\n\n"
            "Перед началом использования бота, пожалуйста, ознакомьтесь и примите наши "
            f"<a href='{terms_url}'>Условия использования</a> и "
            f"<a href='{privacy_url}'>Политику конфиденциальности</a>.\n\n"
            "Нажимая кнопку 'Принимаю', вы подтверждаете свое согласие с этими документами."
        )
        await message.answer(agreement_text, reply_markup=keyboards.create_agreement_keyboard(), disable_web_page_preview=True)
        await state.set_state(UserAgreement.waiting_for_agreement)

@user_router.callback_query(UserAgreement.waiting_for_agreement, F.data == "agree_to_terms")
async def agree_to_terms_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    
    set_terms_agreed(user_id)
    
    await state.clear()
    
    await callback.message.delete()
    
    await callback.message.answer(
        f"✅ Спасибо! Приятного использования.",
        reply_markup=keyboards.main_reply_keyboard
    )
    await show_main_menu(callback.message)

@user_router.message(UserAgreement.waiting_for_agreement)
async def agreement_fallback_handler(message: types.Message):
    await message.answer("Пожалуйста, сначала примите условия использования, нажав на кнопку выше.")

@user_router.message(F.text == "🏠 Главное меню")
async def main_menu_handler(message: types.Message):
    await show_main_menu(message)

@user_router.callback_query(F.data == "back_to_main_menu")
async def back_to_main_menu_handler(callback: types.CallbackQuery):
    await callback.answer()
    await show_main_menu(callback.message, edit_message=True)

@user_router.callback_query(F.data == "show_profile")
async def profile_handler_callback(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    user_db_data = get_user(user_id)
    user_keys = get_user_keys(user_id)
    if not user_db_data:
        await callback.answer("Не удалось получить данные профиля.", show_alert=True)
        return
    username = html.bold(user_db_data.get('username', 'Пользователь'))
    total_spent, total_months = user_db_data.get('total_spent', 0), user_db_data.get('total_months', 0)
    now = datetime.now()
    active_keys = [key for key in user_keys if datetime.fromisoformat(key['expiry_date']) > now]
    if active_keys:
        latest_key = max(active_keys, key=lambda k: datetime.fromisoformat(k['expiry_date']))
        latest_expiry_date = datetime.fromisoformat(latest_key['expiry_date'])
        time_left = latest_expiry_date - now
        vpn_status_text = get_vpn_active_text(time_left.days, time_left.seconds // 3600)
    elif user_keys: vpn_status_text = VPN_INACTIVE_TEXT
    else: vpn_status_text = VPN_NO_DATA_TEXT
    ref_code = ensure_user_ref_code(user_id)
    ref_count = count_referrals(ref_code)
    final_text = get_profile_text(username, total_spent, total_months, vpn_status_text) + f"\n\n👥 Ваш реф-код: <code>{ref_code}</code>\nПриглашено: {ref_count}"
    await callback.message.edit_text(final_text, reply_markup=keyboards.create_back_to_menu_keyboard())

@user_router.callback_query(F.data == "show_referrals")
async def referrals_handler(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    ref_code = ensure_user_ref_code(user_id)
    ref_count = count_referrals(ref_code)
    
    ref_text = (
        f"👥 <b>Реферальная программа</b>\n\n"
        f"🔗 <b>Ваш реф-код:</b> <code>{ref_code}</code>\n"
        f"👥 <b>Приглашено:</b> {ref_count} человек\n\n"
        f"💡 <b>Как это работает:</b>\n"
        f"• Пригласите друга по вашей ссылке\n"
        f"• При покупке подписки вы оба получите +3 дня\n"
        f"• Делитесь ссылкой и получайте бонусы!\n\n"
        f"🔗 <b>Ваша реферальная ссылка:</b>\n"
        f"https://t.me/{(await callback.bot.get_me()).username}?start=ref_{ref_code}"
    )
    
    await callback.message.edit_text(ref_text, reply_markup=keyboards.create_back_to_menu_keyboard())

@user_router.callback_query(F.data == "show_about")
async def about_handler(callback: types.CallbackQuery):
    await callback.answer()
    
    about_text = get_setting("about_text")
    terms_url = get_setting("terms_url")
    privacy_url = get_setting("privacy_url")

    if about_text == ABOUT_TEXT and terms_url == TERMS_URL and privacy_url == PRIVACY_URL:
        await callback.message.edit_text(
            "Информация о проекте не установлена. Установите её в админ-панели.",
            reply_markup=keyboards.create_back_to_menu_keyboard()
        )
    elif terms_url == TERMS_URL and privacy_url == PRIVACY_URL:
        await callback.message.edit_text(
            about_text,
            reply_markup=keyboards.create_back_to_menu_keyboard()
        )
    elif terms_url == TERMS_URL:
        await callback.message.edit_text(
            about_text,
            reply_markup=keyboards.create_about_keyboard_terms(privacy_url)
        )
    elif privacy_url == PRIVACY_URL:
        await callback.message.edit_text(
            about_text,
            reply_markup=keyboards.create_about_keyboard_privacy(terms_url)
        )
    else:
        await callback.message.edit_text(
        about_text,
        reply_markup=keyboards.create_about_keyboard(terms_url, privacy_url)
        )

@user_router.callback_query(F.data == "show_traffic")
async def traffic_status_handler(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    keys = get_user_keys(user_id)
    if not keys:
        await callback.message.edit_text("У вас нет ключей для отображения трафика.", reply_markup=keyboards.create_back_to_menu_keyboard())
        return
    from shop_bot.modules.remnawave_api import get_user_by_telegram_id
    from shop_bot.config import build_progress_bar
    async with aiohttp.ClientSession() as session:
        lines = ["<b>📊 Использование трафика</b>"]
        
        # Получаем общую информацию о пользователе (теперь все ключи в одном профиле)
        remote = await get_user_by_telegram_id(session, str(user_id))
        if not remote:
            lines.append("❌ Не удалось получить данные с сервера")
        else:
            used = remote.get('usedTrafficBytes', 0)
            base_limit = remote.get('trafficLimitBytes', 0)
            
            # Суммируем дополнительный трафик из всех ключей
            total_extra = sum(key.get('traffic_extra_bytes', 0) or 0 for key in keys)
            limit = base_limit + total_extra
            
            if limit > 0:
                percent = min(100, (used/limit)*100)
                bar = build_progress_bar(percent)
                used_gb = used / (1024**3)
                limit_gb = limit / (1024**3)
                
                lines.append(f"📊 Общее использование:")
                lines.append(f"{bar} {percent:.1f}%")
                lines.append(f"📈 {used_gb:.2f} ГБ из {limit_gb:.1f} ГБ")
                
                if total_extra > 0:
                    extra_gb = total_extra / (1024**3)
                    lines.append(f"➕ Доп. трафик: {extra_gb:.1f} ГБ")
            else:
                lines.append("♾️ Безлимитный трафик")
        
        # Показываем информацию о ключах
        lines.append(f"\n🔑 Активных ключей: {len(keys)}")
        for idx, key in enumerate(keys, start=1):
            expiry_date = datetime.fromisoformat(key['expiry_date'])
            status = "✅" if expiry_date > datetime.now() else "❌"
            lines.append(f"{status} Ключ #{idx}: до {expiry_date.strftime('%d.%m.%Y')}")
            
    lines.append("\nНажмите 'Обновить' для актуализации.")
    await callback.message.edit_text("\n".join(lines), reply_markup=keyboards.create_traffic_keyboard())

@user_router.callback_query(F.data == "refresh_traffic")
async def refresh_traffic_handler(callback: types.CallbackQuery):
    await traffic_status_handler(callback)

@user_router.callback_query(F.data == "show_help")
async def about_handler(callback: types.CallbackQuery):
    await callback.answer()

    support_user = get_setting("support_user")
    support_text = get_setting("support_text")

    if support_user == SUPPORT_USER and support_text == SUPPORT_TEXT:
        await callback.message.edit_text(
            support_user,
            reply_markup=keyboards.create_back_to_menu_keyboard()
        )
    elif support_text == SUPPORT_TEXT:
        await callback.message.edit_text(
            "Для связи с поддержкой используйте кнопку ниже.",
            reply_markup=keyboards.create_support_keyboard(support_user)
        )
    else:
        await callback.message.edit_text(
            support_text + "\n\n" + "Для связи с поддержкой используйте кнопку ниже.",
            reply_markup=keyboards.create_support_keyboard(support_user)
        )

@user_router.callback_query(F.data == "manage_keys")
async def manage_keys_handler(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    user_keys = get_user_keys(user_id)
    await callback.message.edit_text(
        "Ваши ключи:" if user_keys else "У вас пока нет ключей, давайте создадим первый!",
        reply_markup=keyboards.create_keys_management_keyboard(user_keys)
    )

@user_router.callback_query(F.data == "toggle_autorenew")
async def toggle_autorenew_handler(callback: types.CallbackQuery):
    await callback.answer()
    uid = callback.from_user.id
    current = get_auto_renew(uid)
    set_auto_renew(uid, not current)
    log_action(uid, 'auto_renew_toggle', str(not current))
    await show_main_menu(callback.message, edit_message=True)

@user_router.callback_query(F.data.startswith("traffic_packs_"))
async def show_traffic_packs(callback: types.CallbackQuery):
    await callback.answer()
    key_id = int(callback.data.split('_')[2])
    await callback.message.edit_text("Выберите пакет дополнительного трафика:", reply_markup=keyboards.create_traffic_packs_keyboard(TRAFFIC_PACKS, key_id))

@user_router.callback_query(F.data.startswith("buy_pack_"))
async def buy_traffic_pack(callback: types.CallbackQuery):
    await callback.answer()
    parts = callback.data.split('_')
    pack_id = parts[2]
    key_id = int(parts[3])
    if pack_id not in TRAFFIC_PACKS:
        await callback.message.edit_text("Пакет не найден", reply_markup=keyboards.create_back_to_key_keyboard(key_id))
        return
    title, price_rub, gb = TRAFFIC_PACKS[pack_id]
    # Используем платеж только как "extend" с особыми метаданными action=pack
    payment_methods = PAYMENT_METHODS
    await callback.message.edit_text(
        f"Покупка пакета: {title}\nОбъем: {gb} ГБ\nЦена: {price_rub} RUB\nВыберите способ оплаты:",
        reply_markup=keyboards.create_payment_method_keyboard(payment_methods, pack_id, "pack", key_id)
    )

@user_router.callback_query(F.data == "enter_promo")
async def enter_promo_info(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("Вы можете ввести промокод перед оплатой. Нажмите кнопку ниже.", reply_markup=keyboards.create_promo_enter_keyboard())

@user_router.callback_query(F.data == "enter_promo_start")
async def enter_promo_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(PromoInput.waiting_for_code)
    await callback.message.edit_text("Введите промокод одним сообщением:")

@user_router.message(PromoInput.waiting_for_code)
async def promo_code_received(message: types.Message, state: FSMContext):
    code = (message.text or '').strip()
    promo = get_promo(code)
    if not promo:
        await message.answer("❌ Промокод недействителен или исчерпан. Попробуйте другой.")
        return
    await state.update_data(promo_code=code)
    discount = promo.get('discount_percent', 0)
    free_days = promo.get('free_days', 0)
    parts = []
    if discount:
        parts.append(f"Скидка {discount}%")
    if free_days:
        parts.append(f"+{free_days} дней")
    await message.answer("✅ Промокод принят: " + ", ".join(parts) + "\nОн будет применён к следующей оплате.")
    await state.clear()
    await show_main_menu(message)

@user_router.callback_query(F.data == "get_trial")
async def trial_period_handler(callback: types.CallbackQuery):
    await callback.answer("Проверяю доступность...", show_alert=False)
    user_id = callback.from_user.id
    user_db_data = get_user(user_id)
    if user_db_data and user_db_data.get('trial_used'):
        await callback.answer("Вы уже использовали бесплатный пробный период.", show_alert=True)
        return
    
    # Устанавливаем флаг использования пробного периода сразу, чтобы предотвратить повторное использование
    set_trial_used(user_id)
    
    await callback.message.edit_text("Отлично! Создаю для вас бесплатный ключ на 3 дня...")
    try:
        key_number = get_next_key_number(user_id)
        email = f"user{user_id}-key{key_number}-trial@kitsura_bot"
        uri, expire_iso, vless_uuid = await remnawave_api.provision_key(email, days=3, telegram_id=str(user_id))
        if not uri or not expire_iso or not vless_uuid:
            # Сбрасываем флаг при ошибке создания ключа
            reset_trial_used(user_id)
            await callback.message.edit_text("❌ Не удалось создать пробный ключ в панели Remnawave.")
            return
        # convert ISO to timestamp ms for storage
        expiry_dt = datetime.fromisoformat(expire_iso.replace('Z', '+00:00'))
        expiry_ms = int(expiry_dt.timestamp() * 1000)
        new_key_id = add_new_key(user_id, vless_uuid, email, expiry_ms)
        
        # Показываем созданный ключ пользователю
        from .keyboards import create_main_menu_keyboard
        expiry_str = expiry_dt.strftime("%d.%m.%Y %H:%M")
        message_text = f"🎉 Ваш бесплатный ключ создан!\n\n"
        message_text += f"📅 Действует до: {expiry_str} UTC\n"
        message_text += f"🔑 Ключ: `{uri}`\n\n"
        message_text += "Скопируйте ключ и добавьте его в ваше VPN-приложение."
        
        # Получаем данные пользователя для клавиатуры
        user_keys = get_user_keys(user_id)
        user_data = get_user(user_id)
        is_admin = str(user_id) == ADMIN_ID
        auto_renew = user_data.get('auto_renew', False) if user_data else False
        
        await callback.message.edit_text(
            message_text,
            parse_mode="Markdown",
            reply_markup=create_main_menu_keyboard(user_keys, trial_available=False, is_admin=is_admin, auto_renew=auto_renew)
        )
    except Exception as e:
        logger.error(f"Error creating trial key for user {user_id}: {e}", exc_info=True)
        # Сбрасываем флаг при любой ошибке
        reset_trial_used(user_id)
        await callback.message.edit_text("❌ Произошла ошибка при создании пробного ключа.")

@user_router.callback_query(F.data == "open_admin_panel")
async def open_admin_panel_handler(callback: types.CallbackQuery):
    if str(callback.from_user.id) != ADMIN_ID:
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    await callback.answer()
    await callback.message.edit_text(
        "Добро пожаловать в админ-панель!",
        reply_markup=keyboards.create_admin_keyboard()
    )

@user_router.callback_query(F.data == "admin_stats")
async def admin_stats_handler(callback: types.CallbackQuery):
    if str(callback.from_user.id) != ADMIN_ID:
        await callback.answer("Нет доступа", show_alert=True); return
    from shop_bot.data_manager.database import get_admin_stats, get_last_backup_timestamp
    stats = get_admin_stats()
    last_backup = get_last_backup_timestamp() or '—'
    
    # Красивое форматирование статистики
    users_count = stats.get('users_count', 0)
    active_keys = stats.get('active_keys', 0)
    total_keys = stats.get('total_keys', 0)
    total_months = stats.get('total_months', 0)
    total_spent = stats.get('total_spent', 0)
    active_promos = stats.get('active_promos', 0)
    total_referrals = stats.get('total_referrals', 0)
    
    # Процент активных ключей
    keys_percentage = round((active_keys / total_keys * 100) if total_keys > 0 else 0, 1)
    
    text = (
        "📊 <b>СТАТИСТИКА БОТА</b>\n"
        "═══════════════════════\n\n"
        
        "👥 <b>ПОЛЬЗОВАТЕЛИ</b>\n"
        f"├ Всего пользователей: <code>{users_count:,}</code>\n"
        f"└ Рефералов привлечено: <code>{total_referrals:,}</code>\n\n"
        
        "🔑 <b>VPN КЛЮЧИ</b>\n"
        f"├ Активных: <code>{active_keys:,}</code> / <code>{total_keys:,}</code>\n"
        f"├ Процент активности: <code>{keys_percentage}%</code>\n"
        f"└ {'🟢' if keys_percentage > 50 else '🟡' if keys_percentage > 25 else '🔴'} "
        f"{'Отлично' if keys_percentage > 50 else 'Нормально' if keys_percentage > 25 else 'Требует внимания'}\n\n"
        
        "💰 <b>ПРОДАЖИ</b>\n"
        f"├ Общая выручка: <code>{total_spent:,.2f} RUB</code>\n"
        f"├ Продано месяцев: <code>{total_months:,}</code>\n"
        f"└ Средний чек: <code>{(total_spent/users_count if users_count > 0 else 0):,.2f} RUB</code>\n\n"
        
        "🎫 <b>ПРОМОКОДЫ</b>\n"
        f"└ Активных: <code>{active_promos:,}</code>\n\n"
        
        "💾 <b>СИСТЕМА</b>\n"
        f"└ Последний бэкап: <code>{last_backup}</code>\n\n"
        
        "═══════════════════════\n"
        f"📅 Обновлено: <code>{datetime.now().strftime('%d.%m.%Y %H:%M')}</code>"
    )
    await callback.message.edit_text(text, reply_markup=keyboards.create_admin_keyboard())

@user_router.callback_query(F.data == "admin_backup")
async def admin_backup_handler(callback: types.CallbackQuery):
    if str(callback.from_user.id) != ADMIN_ID:
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    await callback.answer("Создаю бэкап...")
    
    # Изменяем сообщение, чтобы показать прогресс
    try:
        await callback.message.edit_text("⏳ Создание бэкапа...", reply_markup=None)
    except Exception:
        pass  # Игнорируем ошибки редактирования
    
    # Используем универсальную функцию для создания бэкапа
    success = await create_backup_and_send(callback.bot, ADMIN_ID, is_auto=False)
    
    if success:
        final_text = "✅ Бэкап успешно создан и отправлен!"
    else:
        final_text = "❌ Ошибка создания бэкапа. Проверьте логи."
    
    try:
        await callback.message.edit_text(final_text, reply_markup=keyboards.create_admin_keyboard())
    except Exception:
        # Если не удается отредактировать, отправляем новое сообщение
        await callback.message.answer(final_text, reply_markup=keyboards.create_admin_keyboard())

@user_router.callback_query(F.data == "admin_promos")
async def admin_promos_menu(callback: types.CallbackQuery):
    if str(callback.from_user.id) != ADMIN_ID:
        await callback.answer("Нет доступа", show_alert=True); return
    await callback.answer()
    await callback.message.edit_text("Управление промокодами:", reply_markup=keyboards.create_admin_promos_keyboard())

@user_router.callback_query(F.data == "admin_promo_create")
async def admin_promo_create_start(callback: types.CallbackQuery, state: FSMContext):
    if str(callback.from_user.id) != ADMIN_ID:
        await callback.answer("Нет доступа", show_alert=True); return
    await callback.answer()
    await state.set_state(PromoCreate.waiting_for_code)
    await callback.message.edit_text("Введите код промокода (латиница/цифры):")

@user_router.message(PromoCreate.waiting_for_code)
async def admin_promo_code(message: types.Message, state: FSMContext):
    code = (message.text or '').strip()
    if not code or len(code) > 32:
        await message.answer("Некорректный код, попробуйте снова.")
        return
    await state.update_data(code=code)
    await state.set_state(PromoCreate.waiting_for_discount)
    await message.answer("Введите скидку % (0 если не нужна):")

@user_router.message(PromoCreate.waiting_for_discount)
async def admin_promo_discount(message: types.Message, state: FSMContext):
    try:
        disc = int(message.text)
        if disc < 0 or disc > 90:
            raise ValueError
    except Exception:
        await message.answer("Укажите число 0-90.")
        return
    await state.update_data(discount=disc)
    await state.set_state(PromoCreate.waiting_for_days)
    await message.answer("Введите бесплатные дни (0 если нет):")

@user_router.message(PromoCreate.waiting_for_days)
async def admin_promo_days(message: types.Message, state: FSMContext):
    try:
        days = int(message.text)
        if days < 0 or days > 365:
            raise ValueError
    except Exception:
        await message.answer("Укажите число 0-365.")
        return
    await state.update_data(free_days=days)
    await state.set_state(PromoCreate.waiting_for_limit)
    await message.answer("Введите лимит использований (0 = без лимита):")

@user_router.message(PromoCreate.waiting_for_limit)
async def admin_promo_limit(message: types.Message, state: FSMContext):
    try:
        limit = int(message.text)
        if limit < 0 or limit > 10000:
            raise ValueError
    except Exception:
        await message.answer("Укажите число 0-10000.")
        return
    data = await state.get_data()
    code = data['code']; disc = data['discount']; free_days = data['free_days']
    ok = create_promo(code, disc, free_days, limit)
    await state.clear()
    if ok:
        await message.answer(f"✅ Промокод '{code}' создан. Скидка {disc}%, +{free_days} дн., лимит {limit or '∞'}.")
    else:
        await message.answer("❌ Ошибка создания промокода.")
    await message.answer("Меню промокодов:", reply_markup=keyboards.create_admin_promos_keyboard())

@user_router.callback_query(F.data == "admin_promo_list")
async def admin_promo_list(callback: types.CallbackQuery):
    if str(callback.from_user.id) != ADMIN_ID:
        await callback.answer("Нет доступа", show_alert=True); return
    promos = get_all_promos()
    if not promos:
        text = "Промокодов нет."
    else:
        lines = ["<b>Список промокодов</b>"]
        for p in promos:
            lines.append(f"{p['code']}: {p['discount_percent']}% / +{p['free_days']}д / использовано {p['uses_count']}/{p['uses_limit'] or '∞'} {'✅' if p['active'] else '⛔'}")
        text = "\n".join(lines)
    await callback.message.edit_text(text, reply_markup=keyboards.create_admin_promos_keyboard())

@user_router.callback_query(F.data.startswith("admin_promo_toggle_"))
async def admin_promo_toggle(callback: types.CallbackQuery):
    if str(callback.from_user.id) != ADMIN_ID:
        await callback.answer("Нет доступа", show_alert=True); return
    code = callback.data.split("admin_promo_toggle_")[1]
    from shop_bot.data_manager.database import get_promo, set_promo_active
    p = get_promo(code)
    was_active = bool(p)
    # Если активен, выключаем; если не найден активный, пробуем включить (существует ли в общем списке)
    if was_active:
        set_promo_active(code, False)
        await callback.answer("Выключено")
    else:
        # нужен доступ к неактивным - получим напрямую
        import sqlite3
        from shop_bot.data_manager.database import DB_FILE
        restored = False
        try:
            with sqlite3.connect(DB_FILE) as conn:
                c = conn.cursor(); c.execute("SELECT code FROM promo_codes WHERE code = ?", (code,))
                if c.fetchone():
                    set_promo_active(code, True); restored = True
        except Exception:
            pass
        await callback.answer("Включено" if restored else "Нет такого кода", show_alert=not restored)
    # Обновим список
    promos = get_all_promos()
    lines = ["<b>Список промокодов</b>"]
    for p in promos:
        lines.append(f"{p['code']}: {p['discount_percent']}% / +{p['free_days']}д / {p['uses_count']}/{p['uses_limit'] or '∞'} {'✅' if p['active'] else '⛔'}")
    await callback.message.edit_text("\n".join(lines), reply_markup=keyboards.create_admin_promos_keyboard())

@user_router.callback_query(F.data.startswith("show_key_"))
async def show_key_handler(callback: types.CallbackQuery):
    key_id_to_show = int(callback.data.split("_")[2])
    await callback.message.edit_text("Загружаю информацию о ключе...")
    user_id = callback.from_user.id
    key_data = get_key_by_id(key_id_to_show)

    if not key_data or key_data['user_id'] != user_id:
        await callback.message.edit_text("❌ Ошибка: ключ не найден.")
        return
        
    try:
        # We cannot re-build original without inbound each time; fetch inbound once
        from shop_bot.modules.remnawave_api import get_inbound, build_vless_uri
        import aiohttp
        async with aiohttp.ClientSession() as session:
            inbound = await get_inbound(session)
            if not inbound:
                await callback.message.edit_text("❌ Ошибка: inbound не найден.")
                return
            user_uuid = key_data['vless_uuid']
            email = key_data['key_email']
            connection_string = build_vless_uri(inbound, user_uuid, email)
            if not connection_string:
                await callback.message.edit_text("❌ Не удалось сгенерировать строку подключения.")
                return
        expiry_date = datetime.fromisoformat(key_data['expiry_date'])
        created_date = datetime.fromisoformat(key_data['created_date'])
        all_user_keys = get_user_keys(user_id)
        key_number = next((i + 1 for i, key in enumerate(all_user_keys) if key['key_id'] == key_id_to_show), 0)
        final_text = get_key_info_text(key_number, expiry_date, created_date, connection_string)
        await callback.message.edit_text(text=final_text, reply_markup=keyboards.create_key_info_keyboard(key_id_to_show))
    except Exception as e:
        logger.error(f"Error showing key {key_id_to_show}: {e}")
        await callback.message.edit_text("❌ Произошла ошибка при получении данных ключа.")

@user_router.callback_query(F.data.startswith("show_qr_"))
async def show_qr_handler(callback: types.CallbackQuery):
    await callback.answer("Генерирую QR-код...")
    key_id = int(callback.data.split("_")[2])
    key_data = get_key_by_id(key_id)
    if not key_data or key_data['user_id'] != callback.from_user.id: return
    
    try:
        from shop_bot.modules.remnawave_api import get_inbound, build_vless_uri
        import aiohttp
        async with aiohttp.ClientSession() as session:
            inbound = await get_inbound(session)
            if not inbound: return
            connection_string = build_vless_uri(inbound, key_data['vless_uuid'], key_data['key_email'])
            if not connection_string: return

        qr_img = qrcode.make(connection_string)
        bio = BytesIO(); qr_img.save(bio, "PNG"); bio.seek(0)
        qr_code_file = BufferedInputFile(bio.read(), filename="vpn_qr.png")
        await callback.message.answer_photo(photo=qr_code_file)
    except Exception as e:
        logger.error(f"Error showing QR for key {key_id}: {e}")

@user_router.callback_query(F.data.startswith("show_instruction_"))
async def show_instruction_handler(callback: types.CallbackQuery):
    await callback.answer()
    key_id = int(callback.data.split("_")[2])

    instruction_text = (
        "<b>Как подключиться?</b>\n\n"
        "1. Скопируйте ключ подключения `vless://...`\\.\n"
        "2. Скачайте приложение, совместимое с Xray/V2Ray:\n"
        "   - <b>Android:</b> V2RayTUN https://play.google.com/store/apps/details?id=com.v2raytun.android&hl=ru\n"
        "   - <b>iOS:</b> V2RayTUN https://apps.apple.com/us/app/v2raytun/id6476628951?platform=iphone\n"
        "   - <b>Windows/Linux:</b> Nekoray 3.26 https://github.com/MatsuriDayo/nekoray/releases/tag/3.26\n"
        "3. Посмотреть и полностью прочитать туториал по использованию ключей можно на: https://web.archive.org/web/20250622005028/https://wiki.aeza.net/nekoray-universal-client.\n"
    )
    
    await callback.message.edit_text(
        instruction_text,
        reply_markup=keyboards.create_back_to_key_keyboard(key_id),
        disable_web_page_preview=True
    )

@user_router.callback_query(F.data == "buy_new_key")
async def buy_new_key_handler(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("Выберите тариф для нового ключа:", reply_markup=keyboards.create_plans_keyboard(PLANS, action="new"))

@user_router.callback_query(F.data.startswith("extend_key_"))
async def extend_key_handler(callback: types.CallbackQuery):
    key_id = int(callback.data.split("_")[2])
    await callback.answer()
    await callback.message.edit_text("Выберите тариф для продления ключа:", reply_markup=keyboards.create_plans_keyboard(PLANS, action="extend", key_id=key_id))

@user_router.callback_query(F.data.startswith("buy_") & F.data.contains("_month"))
async def choose_payment_method_handler(callback: types.CallbackQuery):
    await callback.answer()
    parts = callback.data.split("_")
    plan_id, action, key_id = "_".join(parts[:-2]), parts[-2], int(parts[-1])
    await callback.message.edit_text(
        CHOOSE_PAYMENT_METHOD_MESSAGE,
        reply_markup=keyboards.create_payment_method_keyboard(PAYMENT_METHODS, plan_id, action, key_id)
    )

@user_router.callback_query(F.data.startswith("pay_yookassa_"))
async def create_yookassa_payment_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Создаю ссылку на оплату...")
    
    parts = callback.data.split("_")[2:]
    plan_id = "_".join(parts[:-2])
    action = parts[-2]
    key_id = int(parts[-1])
    
    if plan_id not in PLANS:
        await callback.message.answer("Произошла ошибка при выборе тарифа.")
        return

    name, price_rub, months = PLANS[plan_id]
    user_id = callback.from_user.id
    chat_id_to_delete = callback.message.chat.id
    message_id_to_delete = callback.message.message_id
    
    try:
        if months == 1:
            description = f"Оплата подписки на 1 месяц"
        elif months <= 5:
            description = f"Оплата подписки на {months} месяца"
        else:
            description = f"Оплата подписки на {months} месяцев"
        data = await state.get_data()
        promo_code = data.get('promo_code')
        amount_value = price_rub
        if promo_code:
            promo = get_promo(promo_code)
            if promo:
                disc = promo.get('discount_percent', 0)
                if disc and 0 < disc < 100:
                    amount_value = f"{float(price_rub) * (100-disc)/100:.2f}"
        payment = Payment.create({
            "amount": {"value": amount_value, "currency": "RUB"},
            "confirmation": {"type": "redirect", "return_url": f"https://t.me/{TELEGRAM_BOT_USERNAME}"},
            "capture": True, "description": description,
            "metadata": {
                "user_id": user_id, "months": months, "price": amount_value,
                "action": action, "key_id": key_id,
                "chat_id": chat_id_to_delete, "message_id": message_id_to_delete,
                "plan_id": plan_id,
                "promo_code": promo_code
            }
        }, uuid.uuid4())
        await callback.message.edit_text(
            "Нажмите на кнопку ниже для оплаты:",
            reply_markup=keyboards.create_payment_keyboard(payment.confirmation.confirmation_url)
        )
    except Exception as e:
        logger.error(f"Failed to create YooKassa payment: {e}", exc_info=True)
        await callback.message.answer("Не удалось создать ссылку на оплату.")

def create_heleket_signature(payload: dict, api_key: str) -> str:
    """
    Создает сигнатуру для API Heleket на основе рабочего примера.
    Использует жестко заданный, отсортированный список ключей для 100% надежности.
    """
    # 1. Жестко заданный список ключей в алфавитном порядке, как в рабочем примере.
    # Это гарантирует правильный порядок и исключает лишние поля вроде 'metadata'.
    keys_for_sign = [
        'amount', 
        'callback_url', 
        'currency', 
        'description', 
        'fail_url', 
        'merchant_id', 
        'order_id', 
        'success_url'
    ]
    
    # 2. Собираем список значений в правильном порядке.
    # Используем простое преобразование в строку str(), как в примере.
    values = [str(payload[key]) for key in keys_for_sign]
    
    # 3. Соединяем значения через двоеточие.
    sign_string = ":".join(values)
    
    # 4. Добавляем API-ключ и хэшируем.
    string_to_hash = sign_string + api_key

    # Отладка, чтобы убедиться, что все верно
    print(f"DEBUG [Final]: String for hashing: '{string_to_hash}'")
    
    return hashlib.sha256(string_to_hash.encode('utf-8')).hexdigest()

@user_router.callback_query(F.data.startswith("pay_crypto_"))
async def create_crypto_payment_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Создаю счет для оплаты в криптовалюте...")
    
    # Ваша логика парсинга callback.data остается без изменений
    parts = callback.data.split("_")[2:]
    plan_id = "_".join(parts[:-2])
    action = parts[-2]
    key_id = int(parts[-1])

    if plan_id not in PLANS:
        await callback.message.answer("Произошла ошибка при выборе тарифа.")
        return

    name, price_rub, months = PLANS[plan_id]
    user_id = callback.from_user.id
    
    # Получаем URL для вебхуков и имя бота из переменных окружения
    crypto_webhook_url = os.getenv("CRYPTO_WEBHOOK_URL")
    bot_username = os.getenv("TELEGRAM_BOT_USERNAME") # Убедитесь, что эта переменная есть

    try:
        if months == 1:
            description = f"Оплата подписки на 1 месяц"
        elif months <= 4:
            description = f"Оплата подписки на {months} месяца"
        else:
            description = f"Оплата подписки на {months} месяцев"
            
        async with aiohttp.ClientSession() as session:
            # 1. Формируем payload со всеми необходимыми полями
            data_state = await state.get_data()
            promo_code = data_state.get('promo_code')
            amount_value = float(price_rub)
            if promo_code:
                promo = get_promo(promo_code)
                if promo:
                    disc = promo.get('discount_percent', 0)
                    if disc and 0 < disc < 100:
                        amount_value = round(float(price_rub) * (100-disc)/100, 2)
            payload = {
                # ---- Поля, участвующие в подписи ----
                "merchant_id": CRYPTO_MERCHANT_ID,
                "amount": amount_value, # со скидкой при наличии
                "currency": "RUB",
                "order_id": str(uuid.uuid4()),
                "description": description,
                "callback_url": crypto_webhook_url,
                "success_url": f"https://t.me/{bot_username}",
                "fail_url": f"https://t.me/{bot_username}",
                # ---- Поля, НЕ участвующие в подписи ----
                "metadata": {
                    "user_id": user_id, "months": months, "price": amount_value, 
                    "action": action, "key_id": key_id,
                    "chat_id": callback.message.chat.id, 
                    "message_id": callback.message.message_id,
                    "plan_id": plan_id,
                    "promo_code": promo_code
                }
            }

            # 2. Создаем подпись с помощью нашей новой, надежной функции
            signature = create_heleket_signature(payload, CRYPTO_API_KEY)

            # 3. Добавляем подпись в payload для отправки
            payload["sign"] = signature
            
            headers = {"Content-Type": "application/json"}
            api_url = "https://api.heleket.com/v1/payment"
            
            # Отладочный вывод финального payload перед отправкой
            # logger.info(f"Sending payload to Heleket: {payload}")
            
            async with session.post(api_url, json=payload, headers=headers) as response:
                response_text = await response.text()
                
                if response.status == 201:
                    data = json.loads(response_text)
                    payment_url = data.get("pay_url")
                    
                    if not payment_url:
                        logger.error(f"Heleket API success, but no pay_url in response: {response_text}")
                        await callback.message.edit_text("❌ Ошибка получения ссылки на оплату.")
                        return

                    await callback.message.edit_text(
                        "✅ Счет создан!\n\nНажмите на кнопку ниже для оплаты криптовалютой:",
                        reply_markup=keyboards.create_payment_keyboard(payment_url)
                    )
                else:
                    logger.error(f"Heleket API error: {response.status} - {response_text}")
                    await callback.message.edit_text("❌ Не удалось создать счет для оплаты криптовалютой.")

    except Exception as e:
        logger.error(f"Exception during crypto payment creation: {e}", exc_info=True)
        await callback.message.edit_text("❌ Произошла критическая ошибка. Попробуйте позже.")

@user_router.callback_query(F.data.startswith("pay_stars_"))
async def create_stars_payment_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer("Создаю счет для оплаты звездами...")
    
    parts = callback.data.split("_")[2:]
    plan_id = "_".join(parts[:-2])
    action = parts[-2]
    key_id = int(parts[-1])
    
    if plan_id not in PLANS:
        await callback.message.answer("Произошла ошибка при выборе тарифа.")
        return

    name, price_rub, months = PLANS[plan_id]
    user_id = callback.from_user.id
    
    # Конвертируем рубли в звезды (примерно 1 рубль = 2 звезды)
    stars_rate = float(os.getenv("STARS_RATE", "2.0"))  # сколько звезд за 1 рубль
    
    data = await state.get_data()
    promo_code = data.get('promo_code')
    amount_value = float(price_rub)
    
    if promo_code:
        promo = get_promo(promo_code)
        if promo:
            disc = promo.get('discount_percent', 0)
            if disc and 0 < disc < 100:
                amount_value = round(float(price_rub) * (100-disc)/100, 2)
    
    stars_amount = int(amount_value * stars_rate)
    
    try:
        if months == 1:
            description = f"Оплата подписки на 1 месяц"
        elif months <= 4:
            description = f"Оплата подписки на {months} месяца"
        else:
            description = f"Оплата подписки на {months} месяцев"
        
        # Создаем инвойс для Telegram Stars
        from aiogram.types import LabeledPrice
        
        # Telegram Stars payload ограничен 128 байтами, поэтому минимизируем данные
        payload_data = {
            "u": user_id,  # user_id
            "m": months,   # months
            "p": amount_value,  # price
            "a": action,   # action
            "k": key_id,   # key_id
            "pl": plan_id, # plan_id
            "pr": promo_code[:10] if promo_code else None,  # promo_code (первые 10 символов)
            "c": callback.message.chat.id,  # chat_id
            "mid": callback.message.message_id  # message_id
        }
        
        invoice = await bot.create_invoice_link(
            title=f"VPN подписка - {name}",
            description=description,
            payload=json.dumps(payload_data, separators=(',', ':')),  # без пробелов
            provider_token="",  # Для Telegram Stars токен должен быть пустым
            currency="XTR",  # Telegram Stars currency
            prices=[LabeledPrice(label=name, amount=stars_amount)]
        )
        
        # Создаем инлайн-кнопку для оплаты
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💫 Оплатить {stars_amount} звездами", url=invoice)]
        ])
        
        await callback.message.edit_text(
            f"💫 Оплата звездами Telegram\n\n"
            f"Стоимость: {stars_amount} ⭐\n"
            f"Период: {months} мес.\n\n"
            f"Нажмите кнопку ниже для оплаты:",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Failed to create Telegram Stars payment: {e}", exc_info=True)
        await callback.message.answer("Не удалось создать счет для оплаты звездами.")

@user_router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: types.PreCheckoutQuery):
    """Обрабатываем предварительную проверку платежа звездами"""
    await pre_checkout_query.answer(ok=True)

@user_router.message(F.successful_payment)
async def successful_payment_handler(message: types.Message, bot: Bot):
    """Обрабатываем успешную оплату звездами"""
    payment = message.successful_payment
    
    try:
        user_id = message.from_user.id
        bot_logger.payment(user_id, "TELEGRAM_STARS", payment.total_amount, "RECEIVED")
        
        payload_data = json.loads(payment.invoice_payload)
        
        # Конвертируем сокращенные ключи обратно в полные для совместимости с process_successful_payment
        metadata = {
            "user_id": payload_data.get("u"),
            "months": payload_data.get("m"),
            "price": payload_data.get("p"),
            "action": payload_data.get("a"),
            "key_id": payload_data.get("k"),
            "plan_id": payload_data.get("pl"),
            "promo_code": payload_data.get("pr"),
            "chat_id": payload_data.get("c"),
            "message_id": payload_data.get("mid")
        }
        
        logger.info(f"Converted metadata: {metadata}")
        await process_successful_payment(bot, metadata)
        bot_logger.payment(user_id, "TELEGRAM_STARS", payment.total_amount, "SUCCESS")
    except Exception as e:
        bot_logger.payment(message.from_user.id, "TELEGRAM_STARS", payment.total_amount, "FAILED")
        logger.error(f"Error processing stars payment: {e}", exc_info=True)
        await message.answer("❌ Ошибка при обработке платежа. Обратитесь в поддержку.")

async def process_successful_payment(bot: Bot, metadata: dict):
    user_id, months, price, action, key_id = map(metadata.get, ['user_id', 'months', 'price', 'action', 'key_id'])
    user_id, months, price, key_id = int(user_id), int(months or 0), float(price), int(key_id)
    promo_code = metadata.get('promo_code')
    plan_id_meta = metadata.get('plan_id')
    chat_id_to_delete = metadata.get('chat_id')
    message_id_to_delete = metadata.get('message_id')
    
    bot_logger.user_action(user_id, "PAYMENT_PROCESSING", f"{action} {months}m {price}₽")
    
    if chat_id_to_delete and message_id_to_delete:
        try:
            await bot.delete_message(chat_id=chat_id_to_delete, message_id=message_id_to_delete)
        except TelegramBadRequest as e:
            logger.warning(f"Could not delete payment message: {e}")

    processing_message = await bot.send_message(chat_id=user_id, text="✅ Оплата получена! Обрабатываю ваш запрос...")
    try:
        if action == 'pack':
            # find GB amount from TRAFFIC_PACKS
            pack = TRAFFIC_PACKS.get(metadata.get('plan_id') or metadata.get('pack_id') or metadata.get('action_id') or '')
            if not pack:
                # fallback parse plan id from metadata (YooKassa doesn't add plan id separately, so months misused). We encoded pack id as plan_id
                pack_id = metadata.get('plan_id') or metadata.get('pack_id') or metadata.get('action')
                pack = TRAFFIC_PACKS.get(pack_id, None)
            if not pack:
                await processing_message.edit_text("❌ Пакет трафика не найден.")
                return
            title, price_label, gb = pack
            key_data = get_key_by_id(key_id)
            if not key_data or key_data['user_id'] != user_id:
                await processing_message.edit_text("❌ Ключ для добавления трафика не найден.")
                return
            email = key_data['key_email']
            server_ok = await add_extra_traffic(email, gb)
            if server_ok:
                add_traffic_extra(key_id, gb)
                log_action(user_id, 'traffic_pack', f"{key_id}:{gb}")
                await processing_message.delete()
                await bot.send_message(user_id, f"✅ Доп. трафик {gb} ГБ добавлен к ключу #{key_id}.")
            else:
                await processing_message.edit_text("❌ Не удалось обновить лимит на сервере.")
            return
        days_to_add = months * 30
        email = ""
        key_number = 0
        if action == "new":
            key_number = get_next_key_number(user_id)
            email = f"user{user_id}-key{key_number}@kitsura_bot"
        elif action == "extend":
            key_data = get_key_by_id(key_id)
            if not key_data or key_data['user_id'] != user_id:
                await processing_message.edit_text("❌ Ошибка: ключ для продления не найден.")
                return
            all_user_keys = get_user_keys(user_id)
            key_number = next((i + 1 for i, key in enumerate(all_user_keys) if key['key_id'] == key_id), 0)
            email = key_data['key_email']
        # Promo / referral adjustments
        if promo_code:
            promo = get_promo(promo_code)
            if promo:
                free_days = promo.get('free_days', 0)
                discount_percent = promo.get('discount_percent', 0)
                if free_days:
                    days_to_add += free_days
                if discount_percent and discount_percent > 0 and discount_percent < 100:
                    discounted = round(price * (100 - discount_percent) / 100, 2)
                    log_action(user_id, 'price_discount_applied', f"{price}->{discounted}({discount_percent}%)")
                    price = discounted
                apply_promo_usage(promo_code)
                log_action(user_id, 'promo_used', promo_code)
        if not has_action(user_id, 'first_purchase'):
            log_action(user_id, 'first_purchase')
            u = get_user(user_id)
            referrer_code = u.get('referred_by') if u else None
            if referrer_code:
                days_to_add += 3
                log_action(user_id, 'ref_bonus_received', referrer_code)
        uri, expire_iso, vless_uuid = await remnawave_api.provision_key(
            email, 
            days=days_to_add, 
            telegram_id=str(user_id)
        )
        if not uri or not expire_iso or not vless_uuid:
            await processing_message.edit_text("❌ Не удалось создать/обновить ключ в Remnawave.")
            return
        expiry_dt = datetime.fromisoformat(expire_iso.replace('Z', '+00:00'))
        expiry_ms = int(expiry_dt.timestamp() * 1000)
        if action == "new":
            key_id = add_new_key(user_id, vless_uuid, email, expiry_ms)
            if plan_id_meta:
                from shop_bot.data_manager.database import set_key_plan
                set_key_plan(key_id, plan_id_meta)
        elif action == "extend":
            update_key_info(key_id, vless_uuid, expiry_ms)
            if plan_id_meta:
                from shop_bot.data_manager.database import set_key_plan
                set_key_plan(key_id, plan_id_meta)
        update_user_stats(user_id, price, months)
        if promo_code:
            log_action(user_id, 'purchase_with_promo', f"{promo_code}:{price}:{months}")
        else:
            log_action(user_id, 'purchase', f"{price}:{months}")
        await processing_message.delete()
        final_text = get_purchase_success_text(action=action, key_number=key_number, expiry_date=expiry_dt, connection_string=uri)
        await bot.send_message(chat_id=user_id, text=final_text, reply_markup=keyboards.create_key_info_keyboard(key_id))
    # FSM промокода очищается после применения при вводе; отдельное хранение не требуется.
    except Exception as e:
        logger.error(f"Error processing payment for user {user_id}: {e}", exc_info=True)
        await processing_message.edit_text("❌ Ошибка при выдаче ключа.")

@user_router.message(F.text)
async def unknown_message_handler(message: types.Message):
    if message.text and message.text.startswith('/'):
        await message.answer("Такой команды не существует. Попробуйте /start.")
        return
        
    await message.answer("Я не понимаю эту команду. Пожалуйста, используйте кнопку '🏠 Главное меню'.")