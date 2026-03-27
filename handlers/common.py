from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from sqlalchemy import select
from database.models import User
from database.engine import async_session
from database.github_sync import save_database
from keyboards.user_kb import main_inline_keyboard, share_contact_keyboard, back_to_main_keyboard
from locales import get_text, get_all_translations
from middlewares.auth import verified_users_cache
from config import config
import asyncio

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, db_user: User, db_session):
    """Shows language selection, phone verification, or dashboard. Handles referral deep-links."""
    args = message.text.split() if message.text else []
    if len(args) > 1 and args[1].isdigit():
        referrer_id = int(args[1])
        if db_user.referred_by is None and referrer_id != db_user.tg_id:
            referrer = await db_session.scalar(
                select(User).where(User.tg_id == referrer_id)
            )
            if referrer:
                db_user.referred_by = referrer_id
                referrer.referral_count += 1
                await db_session.commit()
                asyncio.create_task(save_database())

    if not db_user.phone_number:
        await message.answer(
            get_text("en", "welcome"),
            parse_mode="HTML",
            reply_markup=share_contact_keyboard("en")
        )
        return
@router.message(F.text == "/debug_me")
async def debug_me(message: Message, db_user: User, db_session):
    import os
    # Refresh to get TRUE state from DB
    await db_session.refresh(db_user)
    
    # Get process ID and list of files
    pid = os.getpid()
    files = ", ".join(os.listdir("."))
    db_url = config.database_url
    
    await message.answer(
        f"🛠 <b>DEBUG INFO V2</b>\n"
        f"PID: {pid}\n"
        f"DB_URL: {db_url}\n"
        f"MEM_PHONE: '{db_user.phone_number}'\n"
        f"FILES: {files[:200]}...",
        parse_mode="HTML"
    )


@router.message(F.text == config.admin_password)
async def handle_secret_password(message: Message, db_user: User):
    if config.admin_password:
        if db_user.tg_id not in config.admin_ids:
            config.admin_ids.append(db_user.tg_id)
            await message.answer("✅ <b>Құпия сөз қабылданды!</b> Сізге админ құқығы берілді.\nПанельді ашу үшін /admin командасын басыңыз.", parse_mode="HTML")
        else:
            await message.answer("ℹ️ Сіз онсыз да админсіз. /admin командасын басыңыз.")



@router.message(F.contact)
async def handle_contact(message: Message, db_user: User, db_session, bot: Bot):
    """Receives shared contact, saves phone, notifies admins."""
    contact = message.contact

    if contact.user_id != message.from_user.id:
        await message.answer(get_text(db_user.language, "contact_error"))
        return

    is_new = db_user.phone_number is None
    db_user.phone_number = contact.phone_number
    verified_users_cache[message.from_user.id] = contact.phone_number
    await db_session.commit()
    asyncio.create_task(save_database())

    await message.answer(
        get_text(db_user.language, "verify_success", phone=contact.phone_number),
        parse_mode="HTML"
    )
    await _show_dashboard(message, db_user)

    if is_new:
        admin_msg = (
            f"🆕 <b>ЖАҢА ПАЙДАЛАНУШЫ ТІРКЕЛДІ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Username: @{message.from_user.username or '—'}\n"
            f"🆔 Telegram ID: <code>{message.from_user.id}</code>\n"
            f"📱 Телефон: <code>{contact.phone_number}</code>\n"
            f"📛 Аты: {message.from_user.full_name}\n"
            f"📅 Тіркелді: {db_user.created_at.strftime('%d.%m.%Y %H:%M')}"
        )
        for admin_id in config.admin_ids:
            try:
                await bot.send_message(admin_id, admin_msg, parse_mode="HTML")
            except Exception:
                pass


async def _show_dashboard(event: Message | CallbackQuery, db_user: User):
    """Renders the Reseller Dashboard."""
    from datetime import datetime, timezone, timedelta
    tz = timezone(timedelta(hours=5))
    now = datetime.now(tz).strftime("%I:%M %p")

    title = get_text(db_user.language, "dashboard_title")
    stats = get_text(db_user.language, "stats")
    bal_text = get_text(db_user.language, "balance")
    spent_text = get_text(db_user.language, "spent")
    status_text = get_text(db_user.language, "status")
    active_text = get_text(db_user.language, "status_active")
    time_text = get_text(db_user.language, "time")

    user_obj = event.from_user
    text = (
        f"{title}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 User: @{user_obj.username or 'no_username'}\n"
        f"🆔 ID: <code>{user_obj.id}</code>\n\n"
        f"{stats}\n"
        f"   {bal_text}: <b>{db_user.balance:,.0f} ₸</b>\n"
        f"   {spent_text}: <b>{db_user.total_spent:,.0f} ₸</b>\n"
        f"   {status_text}: {active_text}\n\n"
        f"{time_text}: {now}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    
    markup = main_inline_keyboard(db_user.language)
    if isinstance(event, Message):
        await event.answer(text, reply_markup=markup, parse_mode="HTML")
    else:
        await event.message.edit_text(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data == "back_to_main")
async def back_to_main_cb(callback: CallbackQuery, db_user: User):
    await _show_dashboard(callback, db_user)
    await callback.answer()


@router.callback_query(F.data == "menu_profile")
async def profile_cb(callback: CallbackQuery, db_user: User):
    title = get_text(db_user.language, "profile_title")
    joined = get_text(db_user.language, "joined")
    bal_text = get_text(db_user.language, "balance")
    spent_text = get_text(db_user.language, "spent")

    text = (
        f"{title}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 ID: <code>{db_user.tg_id}</code>\n"
        f"👤 Username: @{callback.from_user.username or 'no_username'}\n"
        f"📱 Phone: <code>{db_user.phone_number or '—'}</code>\n\n"
        f"{bal_text}: <b>{db_user.balance:,.0f} ₸</b>\n"
        f"{spent_text}: <b>{db_user.total_spent:,.0f} ₸</b>\n"
        f"{joined}: {db_user.created_at.strftime('%d.%m.%Y')}"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_main_keyboard(db_user.language))
    await callback.answer()


@router.callback_query(F.data == "menu_referral")
async def referral_cb(callback: CallbackQuery, db_user: User):
    bot_info = await callback.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={db_user.tg_id}"
    
    bonus_text = ""
    if db_user.referral_bonus > 0:
        bonus_text = get_text(db_user.language, "ref_bonus", bonus=db_user.referral_bonus)
        
    text = get_text(db_user.language, "ref_sys", link=ref_link, count=db_user.referral_count) + bonus_text
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_main_keyboard(db_user.language))
    await callback.answer()


@router.callback_query(F.data == "menu_links")
async def links_cb(callback: CallbackQuery, db_user: User):
    title = get_text(db_user.language, "links_title")
    text = (
        f"{title}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🌐 <a href='{config.official_website}'>Official Website</a>\n"
        f"⬇️ <a href='{config.download_link}'>Download DRIP CLIENT</a>\n"
        f"📢 <a href='{config.telegram_channel}'>Telegram Channel</a>\n"
        f"💬 <a href='{config.contact_admin}'>Contact Admin</a>"
    )
    await callback.message.edit_text(
        text, 
        parse_mode="HTML", 
        disable_web_page_preview=True,
        reply_markup=back_to_main_keyboard(db_user.language)
    )
    await callback.answer()

