"""
GitHub-based persistent storage.

Architecture:
  - SQLite is the runtime DB (fast, transactional).
  - GitHub stores database.json as the backup / restore source.
  - On bot startup  → load_database()  → GitHub JSON → upsert into SQLite
  - On data change  → save_database()  → SQLite dump → push to GitHub

JSON schema (ALL data that must survive a server reset):
{
  "users": {
    "<tg_id>": {
      "tg_id", "username", "phone_number",
      "balance", "total_spent",
      "is_banned", "is_vip",
      "referred_by", "referral_count", "referral_bonus",
      "created_at"
    }
  },
  "vip_codes": {
    "<code>": { "is_used", "used_by", "created_at" }
  },
  "keys": {
    "<key_id>": { "product_id", "key_value", "is_used", "used_by", "created_at" }
  },
  "purchases": {
    "<purchase_id>": { "user_tg_id", "product_id", "key_id", "price", "timestamp" }
  },
  "referrals": [
    { "referee_tg_id", "referrer_tg_id", "joined_at" }
  ],
  "products": { "<id>": { "id", "name", "price", "description" } }
}
"""

import asyncio
import base64
import json
import logging
from datetime import datetime

import aiohttp
from sqlalchemy import select

from config import config
from database.engine import async_session
from database.models import User, Product, VipCode, Purchase, Key

log = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _headers() -> dict:
    return {
        "Authorization": f"Bearer {config.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _enabled() -> bool:
    return bool(config.github_token and config.github_repo)


# ─── Low-level GitHub API ─────────────────────────────────────────────────────

async def _fetch_file() -> tuple[str | None, str | None]:
    """Returns (content_str, sha) or (None, None) if file doesn't exist."""
    url = f"{GITHUB_API}/repos/{config.github_repo}/contents/{config.github_db_file}"
    async with aiohttp.ClientSession() as http:
        async with http.get(url, headers=_headers()) as resp:
            if resp.status == 404:
                return None, None
            if resp.status != 200:
                log.error("GitHub fetch error: %s %s", resp.status, await resp.text())
                return None, None
            data = await resp.json()
            content = base64.b64decode(data["content"]).decode("utf-8")
            return content, data["sha"]


async def _push_file(content: str, sha: str | None, message: str) -> bool:
    """Creates or updates the file on GitHub. Returns True on success."""
    url = f"{GITHUB_API}/repos/{config.github_repo}/contents/{config.github_db_file}"
    payload: dict = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
    }
    if sha:
        payload["sha"] = sha

    async with aiohttp.ClientSession() as http:
        async with http.put(url, headers=_headers(), json=payload) as resp:
            if resp.status in (200, 201):
                return True
            log.error("GitHub push error: %s %s", resp.status, await resp.text())
            return False


# ─── Export SQLite → JSON ─────────────────────────────────────────────────────

async def _dump_to_dict() -> dict:
    async with async_session() as session:

        all_users     = (await session.execute(select(User))).scalars().all()
        all_products  = (await session.execute(select(Product))).scalars().all()
        all_vipcodes  = (await session.execute(select(VipCode))).scalars().all()
        all_keys      = (await session.execute(select(Key))).scalars().all()
        all_purchases = (await session.execute(select(Purchase))).scalars().all()

        # ── 1. USERS (all fields including referral) ──────────────────────────
        users = {
            str(u.tg_id): {
                "tg_id":          u.tg_id,
                "username":       u.username,
                "phone_number":   u.phone_number,
                # Balance & spending
                "balance":        u.balance,
                "total_spent":    u.total_spent,
                # Status
                "is_banned":      u.is_banned,
                "is_vip":         u.is_vip,
                # Referral
                "referred_by":    u.referred_by,
                "referral_count": u.referral_count,
                "referral_bonus": u.referral_bonus,
                # Meta
                "created_at":     u.created_at.isoformat() if u.created_at else None,
            }
            for u in all_users
        }

        # ── 2. VIP CODES ──────────────────────────────────────────────────────
        vip_codes = {
            v.code: {
                "is_used":    v.is_used,
                "used_by":    v.used_by,      # tg_id of the activating user, or null
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in all_vipcodes
        }

        # ── 3. KEYS ───────────────────────────────────────────────────────────
        keys = {
            str(k.id): {
                "product_id": k.product_id,
                "key_value":  k.key_value,
                "is_used":    k.is_used,
                "used_by":    k.used_by,
                "created_at": k.created_at.isoformat() if k.created_at else None,
            }
            for k in all_keys
        }

        # ── 3.5 PURCHASES ─────────────────────────────────────────────────────
        purchases = {
            str(pu.id): {
                "user_tg_id": pu.user_tg_id,
                "product_id": pu.product_id,
                "key_id":     pu.key_id,
                "price":      pu.price,
                "timestamp":  pu.timestamp.isoformat() if pu.timestamp else None,
            }
            for pu in all_purchases
        }

        # ── 4. REFERRALS (denormalised for fast restore) ──────────────────────
        referrals = [
            {
                "referee_tg_id":  u.tg_id,
                "referrer_tg_id": u.referred_by,
                "joined_at":      u.created_at.isoformat() if u.created_at else None,
            }
            for u in all_users if u.referred_by is not None
        ]

        # ── 5. PRODUCTS ───────────────────────────────────────────────────────
        products = {
            str(p.id): {
                "id":          p.id,
                "name":        p.name,
                "price":       p.price,
                "vip_price":   p.vip_price,
                "description": p.description,
            }
            for p in all_products
        }

    return {
        "users":            users,
        "vip_codes":        vip_codes,
        "keys":             keys,
        "purchases":        purchases,
        "referrals":        referrals,
        "products":         products,
        # Metadata
        "_meta": {
            "total_users":     len(users),
            "total_vip_users": sum(1 for u in users.values() if u["is_vip"]),
            "total_keys":      len(keys),
            "total_purchases": len(purchases),
            "total_referrals": len(referrals),
            "last_saved":      datetime.utcnow().isoformat() + "Z",
        },
    }


# ─── Import JSON → SQLite ─────────────────────────────────────────────────────

async def _load_from_dict(data: dict) -> None:
    async with async_session() as session:

        # --- Products first (FK dependency) ---
        for pid, p in data.get("products", {}).items():
            existing = await session.get(Product, int(pid))
            if not existing:
                session.add(Product(
                    id=int(pid),
                    name=p["name"],
                    price=p["price"],
                    vip_price=p.get("vip_price"),
                    description=p.get("description"),
                ))
            else:
                existing.name        = p["name"]
                existing.price       = p["price"]
                existing.vip_price   = p.get("vip_price")
                existing.description = p.get("description")

        # --- Users ---
        for tg_str, u in data.get("users", {}).items():
            tg_id    = int(tg_str)
            existing = await session.scalar(select(User).where(User.tg_id == tg_id))
            if not existing:
                session.add(User(
                    tg_id=tg_id,
                    username=u.get("username"),
                    phone_number=u.get("phone_number"),
                    balance=u.get("balance", 0.0),
                    total_spent=u.get("total_spent", 0.0),
                    is_banned=u.get("is_banned", False),
                    is_vip=u.get("is_vip", False),
                    referred_by=u.get("referred_by"),
                    referral_count=u.get("referral_count", 0),
                    referral_bonus=u.get("referral_bonus", 0.0),
                ))
            else:
                existing.username       = u.get("username")
                existing.phone_number   = u.get("phone_number")
                existing.balance        = u.get("balance",        existing.balance)
                existing.total_spent    = u.get("total_spent",    existing.total_spent)
                existing.is_banned      = u.get("is_banned",      existing.is_banned)
                existing.is_vip         = u.get("is_vip",         existing.is_vip)
                existing.referred_by    = u.get("referred_by",    existing.referred_by)
                existing.referral_count = u.get("referral_count", existing.referral_count)
                existing.referral_bonus = u.get("referral_bonus", existing.referral_bonus)

        # --- VIP codes ---
        for code, v in data.get("vip_codes", {}).items():
            existing = await session.scalar(select(VipCode).where(VipCode.code == code))
            if not existing:
                session.add(VipCode(
                    code=code,
                    is_used=v.get("is_used", False),
                    used_by=v.get("used_by"),
                ))
            else:
                existing.is_used = v.get("is_used", existing.is_used)
                existing.used_by = v.get("used_by", existing.used_by)

        # --- Keys ---
        for kid_str, k in data.get("keys", {}).items():
            kid = int(kid_str)
            existing = await session.get(Key, kid)
            if not existing:
                session.add(Key(
                    id=kid,
                    product_id=k["product_id"],
                    key_value=k["key_value"],
                    is_used=k.get("is_used", False),
                    used_by=k.get("used_by"),
                ))
            else:
                existing.product_id = k["product_id"]
                existing.key_value  = k["key_value"]
                existing.is_used    = k.get("is_used", existing.is_used)
                existing.used_by    = k.get("used_by", existing.used_by)

        # --- Purchases ---
        for pid_str, p in data.get("purchases", {}).items():
            pid = int(pid_str)
            existing = await session.get(Purchase, pid)
            if not existing:
                session.add(Purchase(
                    id=pid,
                    user_tg_id=p["user_tg_id"],
                    product_id=p["product_id"],
                    key_id=p["key_id"],
                    price=p.get("price", 0.0),
                ))

        await session.commit()

    log.info(
        "GitHub sync: loaded — %d products, %d users, %d keys, %d purchases.",
        len(data.get("products", {})),
        len(data.get("users", {})),
        len(data.get("keys", {})),
        len(data.get("purchases", {})),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

async def load_database() -> None:
    """
    On startup: fetch database.json from GitHub and upsert into local SQLite.
    Safe to call even if the file doesn't exist yet.
    """
    if not _enabled():
        log.warning("GitHub sync disabled (GITHUB_TOKEN or GITHUB_REPO not set).")
        return

    log.info("GitHub sync: downloading database.json …")
    content, sha = await _fetch_file()
    if content is None:
        log.info("GitHub sync: no remote database.json — starting fresh.")
        return

    try:
        data = json.loads(content)
        await _load_from_dict(data)
    except Exception as exc:
        log.error("GitHub sync: load failed: %s", exc, exc_info=True)


async def save_database() -> None:
    """
    After any mutation: dump SQLite → JSON → push to GitHub.
    Fire-and-forget safe — errors are logged, never raised.
    """
    if not _enabled():
        return

    try:
        data    = await _dump_to_dict()
        content = json.dumps(data, ensure_ascii=False, indent=2)
        _, sha  = await _fetch_file()
        ts      = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        ok      = await _push_file(content, sha, f"bot: auto-sync {ts}")
        if ok:
            log.info(
                "GitHub sync: pushed OK — users=%d, keys=%d, purchases=%d",
                data["_meta"]["total_users"],
                data["_meta"]["total_keys"],
                data["_meta"]["total_purchases"]
            )
    except Exception as exc:
        log.error("GitHub sync: save failed: %s", exc, exc_info=True)
