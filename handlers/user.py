from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import User, Product, Key
from keyboards.user_kb import main_inline_keyboard, products_keyboard, back_to_main_keyboard
from locales import get_text, get_all_translations

router = Router()


# ─── PRODUCTS ────────────────────────────────────────────────────

@router.callback_query(F.data == "menu_products")
async def products_cb(callback: CallbackQuery, db_user: User, db_session: AsyncSession):
    result = await db_session.execute(select(Product))
    products = result.scalars().all()

    if not products:
        await callback.message.edit_text(
            get_text(db_user.language, "products_empty"),
            reply_markup=back_to_main_keyboard(db_user.language)
        )
        return

    title = get_text(db_user.language, "products_title")
    vip_text = get_text(db_user.language, "vip_price_active") if db_user.is_vip else ""
    bal_text = get_text(db_user.language, "balance")

    text = (
        f"{title}\n\n"
        f"{vip_text}\n"
        f"{bal_text}: <b>{db_user.balance:,.0f} ₸</b>"
    )
    await callback.message.edit_text(
        text,
        reply_markup=products_keyboard(products, is_vip=db_user.is_vip, lang=db_user.language),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("buy_"))
async def buy_product_cb(callback: CallbackQuery, db_user: User, db_session: AsyncSession):
    product_id = int(callback.data.split("_")[1])

    from services.key_allocator import process_purchase
    success, msg = await process_purchase(db_session, db_user, product_id)

    if success:
        success_text = get_text(db_user.language, "buy_success", msg=msg, balance=db_user.balance)
        await callback.message.edit_text(
            success_text,
            parse_mode="HTML",
            reply_markup=main_inline_keyboard(db_user.language)
        )
    else:
        await callback.answer(f"❌ {msg}", show_alert=True)

    await callback.answer()


# ─── MY KEYS ─────────────────────────────────────────────────────

@router.callback_query(F.data == "menu_keys")
async def my_keys_cb(callback: CallbackQuery, db_user: User, db_session: AsyncSession):
    from sqlalchemy.orm import selectinload
    
    result = await db_session.execute(
        select(Key)
        .options(selectinload(Key.product), selectinload(Key.purchase))
        .where(Key.used_by == db_user.tg_id)
        .order_by(Key.id.desc())
    )
    keys = result.scalars().all()

    if not keys:
        await callback.message.edit_text(
            get_text(db_user.language, "keys_empty"),
            reply_markup=back_to_main_keyboard(db_user.language)
        )
        return

    title = get_text(db_user.language, "keys_title")
    text = f"{title}\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for key in keys:
        if key.purchase and key.purchase.timestamp:
            dt = key.purchase.timestamp.strftime("%d.%m.%Y %H:%M")
        elif key.created_at:
            dt = key.created_at.strftime("%d.%m.%Y %H:%M")
        else:
            dt = "Белгісіз"
            
        text += f"📦 <b>{key.product.name}</b>\n🔑 <code>{key.key_value}</code>\n🕒 <i>{dt}</i>\n\n"

    await callback.message.edit_text(
        text, 
        parse_mode="HTML",
        reply_markup=back_to_main_keyboard(db_user.language)
    )
    await callback.answer()
