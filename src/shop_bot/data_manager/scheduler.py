import asyncio
import logging
from datetime import datetime, timezone
import shutil
from pathlib import Path
from aiogram import Bot
from shop_bot.data_manager import database
from shop_bot.modules import remnawave_api
import aiohttp

CHECK_INTERVAL_SECONDS = 300
EXPIRY_NOTIFY_DAYS = [7, 3, 1, 0]
logger = logging.getLogger(__name__)

THRESHOLDS = [50, 80, 90, 100]

async def start_subscription_monitor(bot: Bot):
    logger.info("Subscription monitor started.")
    BACKUP_INTERVAL_HOURS = 6
    last_backup_hour_mark = None
    while True:
        try:
            vpn_users = database.get_all_vpn_users()
            if not vpn_users:
                await asyncio.sleep(CHECK_INTERVAL_SECONDS)
                continue
            async with aiohttp.ClientSession() as session:
                for user_entry in vpn_users:
                    user_id = user_entry['user_id']
                    user_profile = database.get_user(user_id)
                    auto_renew = user_profile.get('auto_renew') if user_profile else 0
                    user_keys = database.get_user_keys(user_id)
                    
                    if not user_keys:
                        continue
                        
                    # Получаем общую информацию о пользователе (теперь все ключи в одном профиле)
                    remote = await remnawave_api.get_user_by_telegram_id(session, str(user_id))
                    if not remote:
                        continue
                        
                    expire_iso = remote.get('expireAt')
                    if not expire_iso:
                        continue
                        
                    try:
                        remote_dt = datetime.fromisoformat(expire_iso.replace('Z', '+00:00'))
                        remote_ms = int(remote_dt.timestamp() * 1000)
                        
                        # Обновляем дату истечения для всех ключей пользователя
                        for key in user_keys:
                            key_email = key['key_email']
                            local_dt = datetime.fromisoformat(key['expiry_date'])
                            local_ms = int(local_dt.timestamp() * 1000)
                            
                            if abs(remote_ms - local_ms) > 1000:
                                class _Obj: pass
                                o = _Obj()
                                o.expiry_time = remote_ms
                                o.id = remote.get('vlessUuid')
                                database.update_key_status_from_server(key_email, o)
                        
                        # Уведомления об истечении (отправляем только один раз для пользователя)
                        # Конвертируем remote_dt в локальное время для корректного сравнения
                        now_local = datetime.now()
                        remote_local = remote_dt.replace(tzinfo=None)  # убираем timezone info
                        days_left = (remote_local - now_local).days
                        last_days_notified = database.get_last_expiry_notified_days(user_id)
                        for mark in EXPIRY_NOTIFY_DAYS:
                            if days_left <= mark and last_days_notified > mark:
                                try:
                                    if mark > 0:
                                        await bot.send_message(user_id, f"⏳ Ваша подписка истекает через {mark} дн.")
                                    else:
                                        await bot.send_message(user_id, f"❗️ Ваша подписка истекла.")
                                except Exception:
                                    pass
                                database.update_last_expiry_notified_days(user_id, mark)
                                break
                        
                        # Auto renew placeholder (применяем к первому ключу)
                        if auto_renew and days_left == 0 and user_keys:
                            key = user_keys[0]  # Берем первый ключ для автопродления
                            try:
                                plan = key.get('subscription_plan') or 'buy_1_month'
                                from shop_bot.config import PLANS
                                name, price_rub, months = PLANS.get(plan, (None, None, 1))
                                extend_days = months * 30
                                key_email = key['key_email']
                                uri, new_expire_iso, new_uuid = await remnawave_api.provision_key(key_email, days=extend_days, telegram_id=str(user_id))
                                if uri and new_expire_iso and new_uuid:
                                    new_dt = datetime.fromisoformat(new_expire_iso.replace('Z', '+00:00'))
                                    # обновим локально для всех ключей пользователя
                                    from shop_bot.data_manager.database import update_key_info, log_action, update_user_stats
                                    for user_key in user_keys:
                                        update_key_info(user_key['key_id'], new_uuid, int(new_dt.timestamp()*1000))
                                    update_user_stats(user_id, float(price_rub) if price_rub else 0.0, months)
                                    log_action(user_id, 'auto_renew_success', f"{key['key_id']}:{months}")
                                    try:
                                        await bot.send_message(user_id, f"🔁 Подписка автоматически продлена на {months} мес. до {new_dt.strftime('%d.%m.%Y %H:%M')}")
                                    except Exception:
                                        pass
                                else:
                                    from shop_bot.data_manager.database import log_action
                                    log_action(user_id, 'auto_renew_fail', str(key['key_id']))
                                    try:
                                        await bot.send_message(user_id, f"⚠️ Автопродление не удалось. Продлите вручную.")
                                    except Exception:
                                        pass
                            except Exception as e:
                                logger.error(f"Auto renew error for user {user_id}: {e}", exc_info=True)
                    
                    except Exception as e:
                        logger.error(f"Error processing user {user_id}: {e}", exc_info=True)
                        continue
                        
                    # Проверка лимитов трафика
                    if remote:
                        limit = remote.get('trafficLimitBytes', 0)
                        used = remote.get('usedTrafficBytes', 0)
                        if not limit or limit <= 0:
                            continue
                        percent = int((used / limit) * 100)
                        last_notified = database.get_key_last_notified_percent(key_email)
                        for th in THRESHOLDS:
                            if percent >= th and last_notified < th:
                                try:
                                    human_used = used/1024/1024/1024
                                    human_limit = limit/1024/1024/1024
                                    await bot.send_message(
                                        chat_id=user_id,
                                        text=(f"⚠️ Трафик ключа {key_email} достиг {th}%\n"
                                              f"Использовано: {human_used:.1f} ГБ из {human_limit:.0f} ГБ.")
                                    )
                                except Exception as e:
                                    logger.warning(f"Failed to send threshold {th}% notification: {e}")
                                database.update_key_last_notified_percent(key_email, th)
                        if percent < 5 and used < 1_000_000 and last_notified >= 50:
                            database.update_key_last_notified_percent(key_email, 0)
        except Exception as e:
            logger.error(f"Monitor loop error: {e}", exc_info=True)
        # Бэкап БД раз в BACKUP_INTERVAL_HOURS
        try:
            now = datetime.utcnow()
            hour_mark = now.hour // BACKUP_INTERVAL_HOURS
            if last_backup_hour_mark != hour_mark:
                db_path = database.DB_FILE
                backups_dir = Path(db_path.parent) / 'backups'
                backups_dir.mkdir(exist_ok=True)
                ts = now.strftime('%Y%m%d_%H%M%S')
                backup_file = backups_dir / f"users_{ts}.db"
                shutil.copy(db_path, backup_file)
                database.set_last_backup_timestamp(now.isoformat())
                # Удалим старше 20 файлов
                files = sorted(backups_dir.glob('users_*.db'))
                if len(files) > 20:
                    for old in files[:-20]:
                        try: old.unlink()
                        except Exception: pass
                last_backup_hour_mark = hour_mark
        except Exception as e:
            logger.error(f"Backup error: {e}")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)