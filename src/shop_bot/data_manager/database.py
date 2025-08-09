import sqlite3
from datetime import datetime
import logging
import os
from pathlib import Path
from shop_bot.config import ABOUT_TEXT, TERMS_URL, PRIVACY_URL, SUPPORT_USER, SUPPORT_TEXT, CHANNEL_URL

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path.cwd()
DB_FILE = PROJECT_ROOT / "users.db"

def initialize_db():
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username TEXT,
                    total_spent REAL DEFAULT 0,
                    total_months INTEGER DEFAULT 0,
                    trial_used BOOLEAN DEFAULT 0,
                    agreed_to_terms BOOLEAN DEFAULT 0,
                    ref_code TEXT UNIQUE,
                    referred_by TEXT,
                    auto_renew BOOLEAN DEFAULT 0,
                    last_expiry_notified_days INTEGER DEFAULT 999
                );
                CREATE TABLE IF NOT EXISTS vpn_keys (
                    key_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    vless_uuid TEXT NOT NULL,
                    key_email TEXT NOT NULL UNIQUE,
                    expiry_date TIMESTAMP,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_notified_percent INTEGER DEFAULT 0,
                    subscription_plan TEXT,
                    traffic_extra_bytes INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS promo_codes (
                    code TEXT PRIMARY KEY,
                    discount_percent INTEGER DEFAULT 0,
                    free_days INTEGER DEFAULT 0,
                    uses_limit INTEGER DEFAULT 0,
                    uses_count INTEGER DEFAULT 0,
                    active BOOLEAN DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_code TEXT,
                    referred_user_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS user_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action TEXT,
                    meta TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS bot_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
            ''')
            default_settings = {
                "about_text": ABOUT_TEXT,
                "terms_url": TERMS_URL,
                "privacy_url": PRIVACY_URL,
                "support_user": SUPPORT_USER,
                "support_text": SUPPORT_TEXT,
                "channel_url": CHANNEL_URL,
            }
            if not cursor.execute("SELECT COUNT(*) FROM bot_settings").fetchone()[0]:
                for key, value in default_settings.items():
                    cursor.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)", (key, value))
            conn.commit()
            logging.info("Database with 'created_date' column initialized successfully.")
    except sqlite3.Error as e:
        logging.error(f"Database error on initialization: {e}")

def get_setting(key: str) -> str | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
            result = cursor.fetchone()
            return result[0] if result else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get setting '{key}': {e}")
        return None

def update_setting(key: str, value: str):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE bot_settings SET value = ? WHERE key = ?", (value, key))
            conn.commit()
            logging.info(f"Setting '{key}' updated.")
    except sqlite3.Error as e:
        logging.error(f"Failed to update setting '{key}': {e}")

def register_user_if_not_exists(telegram_id: int, username: str):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT telegram_id FROM users WHERE telegram_id = ?", (telegram_id,))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO users (telegram_id, username) VALUES (?, ?)", (telegram_id, username))
            else:
                cursor.execute("UPDATE users SET username = ? WHERE telegram_id = ?", (username, telegram_id))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to register user {telegram_id}: {e}")

def get_user(telegram_id: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            user_data = cursor.fetchone()
            return dict(user_data) if user_data else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get user {telegram_id}: {e}")
        return None

def set_terms_agreed(telegram_id: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET agreed_to_terms = 1 WHERE telegram_id = ?", (telegram_id,))
            conn.commit()
            logging.info(f"User {telegram_id} has agreed to terms.")
    except sqlite3.Error as e:
        logging.error(f"Failed to set terms agreed for user {telegram_id}: {e}")

def update_user_stats(telegram_id: int, amount_spent: float, months_purchased: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET total_spent = total_spent + ?, total_months = total_months + ? WHERE telegram_id = ?", (amount_spent, months_purchased, telegram_id))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to update user stats for {telegram_id}: {e}")

def set_trial_used(telegram_id: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET trial_used = 1 WHERE telegram_id = ?", (telegram_id,))
            conn.commit()
            logging.info(f"Trial period marked as used for user {telegram_id}.")
    except sqlite3.Error as e:
        logging.error(f"Failed to set trial used for user {telegram_id}: {e}")

def reset_trial_used(telegram_id: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET trial_used = 0 WHERE telegram_id = ?", (telegram_id,))
            conn.commit()
            logging.info(f"Trial period reset for user {telegram_id}.")
    except sqlite3.Error as e:
        logging.error(f"Failed to reset trial for user {telegram_id}: {e}")

def add_new_key(user_id: int, vless_uuid: str, key_email: str, expiry_timestamp_ms: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # Конвертируем UTC timestamp в локальное время корректно
            from datetime import timezone
            expiry_date = datetime.fromtimestamp(expiry_timestamp_ms / 1000, tz=timezone.utc).replace(tzinfo=None)
            created_date = datetime.now()
            cursor.execute(
                "INSERT INTO vpn_keys (user_id, vless_uuid, key_email, expiry_date, created_date) VALUES (?, ?, ?, ?, ?)",
                (user_id, vless_uuid, key_email, expiry_date, created_date)
            )
            new_key_id = cursor.lastrowid
            conn.commit()
            return new_key_id
    except sqlite3.Error as e:
        logging.error(f"Failed to add new key for user {user_id}: {e}")
        return None

def get_user_keys(user_id: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vpn_keys WHERE user_id = ? ORDER BY key_id", (user_id,))
            keys = cursor.fetchall()
            return [dict(key) for key in keys]
    except sqlite3.Error as e:
        logging.error(f"Failed to get keys for user {user_id}: {e}")
        return []

def get_key_by_id(key_id: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vpn_keys WHERE key_id = ?", (key_id,))
            key_data = cursor.fetchone()
            return dict(key_data) if key_data else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get key by ID {key_id}: {e}")
        return None

def update_key_info(key_id: int, new_vless_uuid: str, new_expiry_ms: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # Конвертируем UTC timestamp в локальное время корректно
            from datetime import timezone
            expiry_date = datetime.fromtimestamp(new_expiry_ms / 1000, tz=timezone.utc).replace(tzinfo=None)
            cursor.execute("UPDATE vpn_keys SET vless_uuid = ?, expiry_date = ? WHERE key_id = ?", (new_vless_uuid, expiry_date, key_id))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to update key {key_id}: {e}")

def get_next_key_number(user_id: int) -> int:
    keys = get_user_keys(user_id)
    return len(keys) + 1

def get_all_vpn_users():
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT user_id FROM vpn_keys")
            users = cursor.fetchall()
            return [dict(user) for user in users]
    except sqlite3.Error as e:
        logging.error(f"Failed to get all vpn users: {e}")
        return []

def update_key_status_from_server(key_email: str, remote_user):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            if remote_user:
                # Конвертируем UTC timestamp в локальное время корректно
                from datetime import timezone
                expiry_date = datetime.fromtimestamp(remote_user.expiry_time / 1000, tz=timezone.utc).replace(tzinfo=None)
                cursor.execute("UPDATE vpn_keys SET vless_uuid = ?, expiry_date = ? WHERE key_email = ?", (remote_user.id, expiry_date, key_email))
            else:
                cursor.execute("DELETE FROM vpn_keys WHERE key_email = ?", (key_email,))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to update key status for {key_email}: {e}")

def update_key_last_notified_percent(key_email: str, percent: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE vpn_keys SET last_notified_percent = ? WHERE key_email = ?", (percent, key_email))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to update last_notified_percent for {key_email}: {e}")

def get_key_last_notified_percent(key_email: str) -> int:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT last_notified_percent FROM vpn_keys WHERE key_email = ?", (key_email,))
            row = cursor.fetchone()
            return row[0] if row and row[0] is not None else 0
    except sqlite3.Error as e:
        logging.error(f"Failed to get last_notified_percent for {key_email}: {e}")
        return 0

# -------------------- Promo codes --------------------
def create_promo(code: str, discount_percent: int, free_days: int, uses_limit: int) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO promo_codes (code, discount_percent, free_days, uses_limit, uses_count, active) VALUES (?, ?, ?, ?, COALESCE((SELECT uses_count FROM promo_codes WHERE code = ?),0), 1)", (code, discount_percent, free_days, uses_limit, code))
            conn.commit(); return True
    except sqlite3.Error as e:
        logging.error(f"Failed to create promo {code}: {e}"); return False

def get_promo(code: str):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row; c = conn.cursor()
            c.execute("SELECT * FROM promo_codes WHERE code = ? AND active = 1", (code,))
            r = c.fetchone(); return dict(r) if r else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get promo {code}: {e}"); return None

def apply_promo_usage(code: str):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("UPDATE promo_codes SET uses_count = uses_count + 1 WHERE code = ?", (code,))
            c.execute("UPDATE promo_codes SET active = 0 WHERE code = ? AND uses_limit > 0 AND uses_count >= uses_limit", (code,))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to update promo usage {code}: {e}")

def get_all_promos():
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor(); c.execute("SELECT * FROM promo_codes ORDER BY code")
            rows = c.fetchall(); return [dict(r) for r in rows]
    except sqlite3.Error as e:
        logging.error(f"Failed to list promos: {e}"); return []

def set_promo_active(code: str, active: bool) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor(); c.execute("UPDATE promo_codes SET active = ? WHERE code = ?", (1 if active else 0, code)); conn.commit(); return c.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to set promo {code} active={active}: {e}"); return False

# -------------------- Referrals --------------------
def ensure_user_ref_code(telegram_id: int) -> str:
    import secrets
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor(); c.execute("SELECT ref_code FROM users WHERE telegram_id = ?", (telegram_id,))
            row = c.fetchone()
            if row and row[0]:
                return row[0]
            new_code = secrets.token_urlsafe(6)
            c.execute("UPDATE users SET ref_code = ? WHERE telegram_id = ?", (new_code, telegram_id))
            conn.commit(); return new_code
    except sqlite3.Error as e:
        logging.error(f"Failed to ensure ref code for {telegram_id}: {e}"); return ""

def link_referral(ref_code: str, new_user_id: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("SELECT telegram_id FROM users WHERE ref_code = ?", (ref_code,))
            owner = c.fetchone()
            if not owner: return False
            
            # Проверка: пользователь не может пригласить сам себя
            if owner[0] == new_user_id:
                logging.warning(f"User {new_user_id} tried to refer themselves with code {ref_code}")
                return False
                
            c.execute("UPDATE users SET referred_by = ? WHERE telegram_id = ? AND referred_by IS NULL", (ref_code, new_user_id))
            c.execute("INSERT INTO referrals (referrer_code, referred_user_id) VALUES (?, ?)", (ref_code, new_user_id))
            conn.commit(); return True
    except sqlite3.Error as e:
        logging.error(f"Failed to link referral {ref_code} -> {new_user_id}: {e}"); return False

def count_referrals(ref_code: str) -> int:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor(); c.execute("SELECT COUNT(*) FROM referrals WHERE referrer_code = ?", (ref_code,))
            return c.fetchone()[0]
    except sqlite3.Error as e:
        logging.error(f"Failed to count referrals for {ref_code}: {e}"); return 0

# -------------------- Auto renew & expiry notifications --------------------
def set_auto_renew(user_id: int, enabled: bool):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor(); c.execute("UPDATE users SET auto_renew = ? WHERE telegram_id = ?", (1 if enabled else 0, user_id)); conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to set auto_renew for {user_id}: {e}")

def get_auto_renew(user_id: int) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor(); c.execute("SELECT auto_renew FROM users WHERE telegram_id = ?", (user_id,)); row = c.fetchone(); return bool(row and row[0])
    except sqlite3.Error as e:
        logging.error(f"Failed to get auto_renew for {user_id}: {e}"); return False

def get_last_expiry_notified_days(user_id: int) -> int:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor(); c.execute("SELECT last_expiry_notified_days FROM users WHERE telegram_id = ?", (user_id,)); row = c.fetchone(); return row[0] if row else 999
    except sqlite3.Error as e:
        logging.error(f"Failed to get last_expiry_notified_days for {user_id}: {e}"); return 999

def update_last_expiry_notified_days(user_id: int, days: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor(); c.execute("UPDATE users SET last_expiry_notified_days = ? WHERE telegram_id = ?", (days, user_id)); conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to update last_expiry_notified_days for {user_id}: {e}")

# -------------------- Actions log --------------------
def log_action(user_id: int, action: str, meta: str | None = None):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor(); c.execute("INSERT INTO user_actions (user_id, action, meta) VALUES (?, ?, ?)", (user_id, action, meta)); conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to log action {action} for {user_id}: {e}")

def add_traffic_extra(key_id: int, gb: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor(); c.execute("UPDATE vpn_keys SET traffic_extra_bytes = traffic_extra_bytes + ? WHERE key_id = ?", (gb * 1024 * 1024 * 1024, key_id)); conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to add extra traffic for key {key_id}: {e}")

def set_key_plan(key_id: int, plan_id: str):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor(); c.execute("UPDATE vpn_keys SET subscription_plan = ? WHERE key_id = ?", (plan_id, key_id)); conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to set plan {plan_id} for key {key_id}: {e}")

def has_action(user_id: int, action: str) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor(); c.execute("SELECT 1 FROM user_actions WHERE user_id = ? AND action = ? LIMIT 1", (user_id, action)); return c.fetchone() is not None
    except sqlite3.Error as e:
        logging.error(f"Failed to check action {action} for {user_id}: {e}"); return False

def get_user_by_ref_code(ref_code: str):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor(); c.execute("SELECT * FROM users WHERE ref_code = ?", (ref_code,)); row = c.fetchone(); return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get user by ref_code {ref_code}: {e}"); return None

# -------------------- Admin stats --------------------
def get_admin_stats():
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*), COALESCE(SUM(total_spent),0), COALESCE(SUM(total_months),0) FROM users")
            users_count, total_spent, total_months = c.fetchone()
            c.execute("SELECT COUNT(*) FROM vpn_keys")
            total_keys = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM vpn_keys WHERE expiry_date > CURRENT_TIMESTAMP")
            active_keys = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM promo_codes WHERE active = 1")
            active_promos = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM referrals")
            total_referrals = c.fetchone()[0]
            return {
                'users_count': users_count,
                'total_spent': total_spent,
                'total_months': total_months,
                'total_keys': total_keys,
                'active_keys': active_keys,
                'active_promos': active_promos,
                'total_referrals': total_referrals,
            }
    except sqlite3.Error as e:
        logging.error(f"Failed to get admin stats: {e}")
        return {}

def set_last_backup_timestamp(ts_iso: str):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor(); c.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('last_backup_iso', ?)", (ts_iso,)); conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to set last backup timestamp: {e}")

def get_last_backup_timestamp() -> str | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor(); c.execute("SELECT value FROM bot_settings WHERE key = 'last_backup_iso'")
            row = c.fetchone(); return row[0] if row else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get last backup timestamp: {e}"); return None