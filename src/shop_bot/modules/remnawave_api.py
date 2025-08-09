import os
import logging
import base64
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import aiohttp
try:
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
    _HAS_CRYPTO = True
except Exception:  # pragma: no cover
    _HAS_CRYPTO = False

logger = logging.getLogger(__name__)

# ENV variables expected:
# REMNA_BASE_URL - e.g. https://panel.domain.com
# REMNA_API_TOKEN - Bearer token with API role (superadmin / API)
# REMNA_COOKIE - session cookie (e.g. olLRagjj=hPCTZLSX)
# REMNA_INBOUND_TAG - tag of inbound (e.g. "VLESS SWE") OR REMNA_INBOUND_UUID
# REMNA_SQUAD_UUID - UUID of internal squad for users
# REMNA_DEFAULT_DAYS - fallback days if not provided (optional)
# REMNA_SERVER_SNI - optional override for SNI (if need to force different host in URI)
# REMNA_FP - fingerprint value for utls (optional)

BASE_URL = os.getenv("REMNA_BASE_URL", "").rstrip("/")
API_TOKEN = os.getenv("REMNA_API_TOKEN")
COOKIE = os.getenv("REMNA_COOKIE")
INBOUND_TAG = os.getenv("REMNA_INBOUND_TAG")
INBOUND_UUID = os.getenv("REMNA_INBOUND_UUID")
SQUAD_UUID = os.getenv("REMNA_SQUAD_UUID")
DEFAULT_DAYS = int(os.getenv("REMNA_DEFAULT_DAYS", "30"))
SERVER_SNI = os.getenv("REMNA_SERVER_SNI")
UTLS_FP = os.getenv("REMNA_FP") or os.getenv("FP")  # reuse old var if present

HEADERS = {"Authorization": f"Bearer {API_TOKEN}"} if API_TOKEN else {}
if COOKIE:
    HEADERS["Cookie"] = COOKIE

class RemnaInbound:
    def __init__(self, uuid: str, tag: str, port: int, network: str, security: str, raw: dict):
        self.uuid = uuid
        self.tag = tag
        self.port = port
        self.network = network
        self.security = security
        self.raw = raw or {}

def _iso_expiry(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).replace(microsecond=0).isoformat().replace('+00:00', 'Z')

async def _fetch_json(session: aiohttp.ClientSession, method: str, path: str, **kwargs) -> Optional[dict]:
    url = f"{BASE_URL}{path}"
    try:
        async with session.request(method, url, headers=HEADERS, **kwargs) as resp:
            txt = await resp.text()
            if resp.status >= 400:
                logger.error(f"Remna API {method} {path} failed {resp.status}: {txt}")
                return None
            try:
                return await resp.json()
            except Exception:
                logger.error(f"Failed to parse JSON from {path}: {txt[:200]}")
                return None
    except Exception as e:
        logger.error(f"HTTP error {method} {path}: {e}")
        return None

_INBOUND_CACHE: Optional[RemnaInbound] = None

async def get_inbound(session: aiohttp.ClientSession, force_refresh: bool = False) -> Optional[RemnaInbound]:
    global _INBOUND_CACHE
    if _INBOUND_CACHE and not force_refresh:
        return _INBOUND_CACHE
    if not BASE_URL or not API_TOKEN:
        logger.error("Remna config incomplete: BASE_URL or API_TOKEN missing")
        return None
    data = await _fetch_json(session, 'GET', '/api/config-profiles/inbounds')
    if not data or 'response' not in data:
        return None
    inbounds = data['response'].get('inbounds', [])
    for inbound in inbounds:
        if INBOUND_UUID and inbound.get('uuid') == INBOUND_UUID:
            raw = inbound.get('rawInbound', {})
            _INBOUND_CACHE = RemnaInbound(inbound['uuid'], inbound['tag'], inbound['port'], inbound['network'], inbound['security'], raw)
            return _INBOUND_CACHE
        if INBOUND_TAG and inbound.get('tag') == INBOUND_TAG:
            raw = inbound.get('rawInbound', {})
            _INBOUND_CACHE = RemnaInbound(inbound['uuid'], inbound['tag'], inbound['port'], inbound['network'], inbound['security'], raw)
            return _INBOUND_CACHE
    logger.error("Desired inbound not found (tag/uuid)")
    return None

async def get_user_by_telegram_id(session: aiohttp.ClientSession, telegram_id: str) -> Optional[dict]:
    data = await _fetch_json(session, 'GET', f'/api/users/by-telegram-id/{telegram_id}')
    if data and 'response' in data:
        resp = data['response']
        if isinstance(resp, list) and resp:
            return resp[0]
        if isinstance(resp, dict):
            return resp
    return None

TRAFFIC_LIMIT_GB = int(os.getenv("REMNA_TRAFFIC_LIMIT_GB", "500"))  # 500 GB default
TRAFFIC_LIMIT_BYTES = TRAFFIC_LIMIT_GB * 1024 * 1024 * 1024
TRAFFIC_STRATEGY = os.getenv("REMNA_TRAFFIC_STRATEGY", "MONTH")  # MONTH resets monthly in panel

async def create_or_extend_user(session: aiohttp.ClientSession, inbound: RemnaInbound, email: str, days_to_add: int, telegram_id: str = None) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Returns (vless_uuid, subscription_url, expire_iso)"""
    existing = None
    if telegram_id:
        existing = await get_user_by_telegram_id(session, telegram_id)
    
    now = datetime.now(timezone.utc)
    if existing:
        # Update existing user
        expire_at_iso = existing.get('expireAt')
        try:
            current_exp = datetime.fromisoformat(expire_at_iso.replace('Z', '+00:00')) if expire_at_iso else now
        except Exception:
            current_exp = now
        base_dt = current_exp if current_exp > now else now
        new_exp = base_dt + timedelta(days=days_to_add)
        new_iso = new_exp.replace(microsecond=0).isoformat().replace('+00:00', 'Z')
        body = {
            "email": email,
            "uuid": existing.get('uuid'),
            "expireAt": new_iso,
            "trafficLimitBytes": TRAFFIC_LIMIT_BYTES,
            "trafficLimitStrategy": TRAFFIC_STRATEGY,
            # НЕ передаем username при обновлении существующего пользователя
        }
        if telegram_id:
            body["telegramId"] = int(telegram_id)
        updated = await _fetch_json(session, 'PATCH', '/api/users', json=body)
        if updated and 'response' in updated:
            u = updated['response']
            return u.get('vlessUuid'), u.get('subscriptionUrl'), u.get('expireAt')
        return None, None, None
    
    # Create new user
    new_iso = _iso_expiry(days_to_add)
    username = (email.split('@')[0])[:32]
    body = {
        "email": email,
        "username": username,
        "expireAt": new_iso,
        "trafficLimitBytes": TRAFFIC_LIMIT_BYTES,
        "trafficLimitStrategy": TRAFFIC_STRATEGY,
    }
    
    # Add telegram ID if provided (convert to int)
    if telegram_id:
        body["telegramId"] = int(telegram_id)
    
    # Add activeInternalSquads if SQUAD_UUID is configured
    if SQUAD_UUID:
        body["activeInternalSquads"] = [SQUAD_UUID]
    
    created = await _fetch_json(session, 'POST', '/api/users', json=body)
    if created and 'response' in created:
        u = created['response']
        return u.get('vlessUuid'), u.get('subscriptionUrl'), u.get('expireAt')
    return None, None, None

def _derive_public_key_from_private(private_b64: str) -> Optional[str]:
    """Derive Reality public key (base64, no padding) from private key if cryptography installed."""
    if not private_b64 or not _HAS_CRYPTO:
        return None
    try:
        priv_bytes = base64.b64decode(private_b64 + '==')  # tolerate missing padding
        priv = X25519PrivateKey.from_private_bytes(priv_bytes)
        pub = priv.public_key().public_bytes()
        b64 = base64.b64encode(pub).decode().rstrip('=').replace('+', '-').replace('/', '_')
        return b64
    except Exception as e:  # pragma: no cover
        logger.debug(f"Failed derive public key: {e}")
        return None

def build_vless_uri(inbound: RemnaInbound, vless_uuid: str, email: str) -> Optional[str]:
    if not inbound or not vless_uuid:
        return None
    reality = inbound.raw.get('streamSettings', {}).get('realitySettings', {})
    server_names = reality.get('serverNames') or []
    short_ids = reality.get('shortIds') or []
    if not server_names or not short_ids:
        logger.error("Reality settings incomplete")
        return None
    sni = SERVER_SNI or server_names[0]
    # NOTE: Remnawave full inbound JSON не возвращает publicKey Reality напрямую (есть только privateKey).
    # Пользователь должен указать REMNA_PUBLIC_KEY в .env (получается при настройке Reality пары ключей в Xray).
    pbk = os.getenv('REMNA_PUBLIC_KEY')
    if not pbk:
        private_key = reality.get('privateKey')
        derived = _derive_public_key_from_private(private_key)
        pbk = derived or 'PUBLIC_KEY_PLACEHOLDER'
    short_id = short_ids[0]
    fp = UTLS_FP or 'chrome'
    host = sni
    port = inbound.port
    flow = os.getenv('REMNA_FLOW', 'xtls-rprx-vision')  # default flow for VLESS Reality
    return (
        f"vless://{vless_uuid}@{host}:{port}?type={inbound.network}&security=reality&flow={flow}&fp={fp}&pbk={pbk}&sni={sni}&sid={short_id}&spx=%2F"
        f"#{inbound.tag}-{email}"
    )

async def provision_key(email: str, days: int | None = None, telegram_id: str = None) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    days = days or DEFAULT_DAYS
    async with aiohttp.ClientSession() as session:
        inbound = await get_inbound(session)
        if not inbound:
            return None, None, None
        vless_uuid, sub_url, expire_iso = await create_or_extend_user(session, inbound, email, days, telegram_id)
        if not vless_uuid:
            return None, None, None
        uri = build_vless_uri(inbound, vless_uuid, email)
        return uri, expire_iso, vless_uuid

async def add_extra_traffic(email: str, extra_gb: int, telegram_id: str = None) -> bool:
    """Увеличивает лимит трафика пользователю на extra_gb (ГБ) на сервере.
    Возвращает True при успехе."""
    bytes_add = extra_gb * 1024 * 1024 * 1024
    async with aiohttp.ClientSession() as session:
        user = None
        if telegram_id:
            user = await get_user_by_telegram_id(session, telegram_id)
        
        if not user:
            return False
        current_limit = user.get('trafficLimitBytes') or 0
        expire_at = user.get('expireAt') or _iso_expiry(DEFAULT_DAYS)
        body = {
            "email": email,
            "uuid": user.get('uuid'),
            "expireAt": expire_at,
            "trafficLimitBytes": current_limit + bytes_add,
            "trafficLimitStrategy": TRAFFIC_STRATEGY,
        }
        if telegram_id:
            body["telegramId"] = int(telegram_id)
        updated = await _fetch_json(session, 'PATCH', '/api/users', json=body)
        return bool(updated and 'response' in updated)

class RemnaWaveAPI:
    def __init__(self, base_url: str, token: str, cookie: str = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.cookie = cookie

    async def _fetch_json(self, endpoint: str):
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "accept": "application/json"
        }
        if self.cookie:
            headers["Cookie"] = self.cookie
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 404:
                    raise Exception(f"Remna API GET {endpoint} failed 404: {await response.text()}")
                response.raise_for_status()
                return await response.json()

    async def get_config_profiles_inbounds(self):
        data = await self._fetch_json("/api/config-profiles/inbounds")
        if "response" in data and "inbounds" in data["response"]:
            return data["response"]["inbounds"]
        else:
            raise Exception("Unexpected response format: missing 'inbounds' key")
