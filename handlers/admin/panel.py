from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from database.models import User, Payment, Purchase, Key, Product
from config import config
from keyboards.admin_kb import admin_panel_keyboard
from keyboards.user_kb import main_inline_keyboard

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in config.admin_ids


@router.message(Command("admin"))
async def admin_start(message: Message, db_user: User):
    if not is_admin(db_user.tg_id):
        await message.answer("⛔ Рұқсат жоқ.")
        return

    await message.answer(
        "🔧 <b>ADMIN PANEL</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 @{message.from_user.username}\n"
        f"Admin IDs: {config.admin_ids}",
        reply_markup=admin_panel_keyboard(),
        parse_mode="HTML"
    )


@router.message(F.text == "🔙 User Mode")
async def user_mode_handler(message: Message, db_user: User):
    if not is_admin(db_user.tg_id):
        return
    await message.answer("↩️ Пайдаланушы режиміне өттіңіз.", reply_markup=main_inline_keyboard())


@router.message(F.text == "📊 Statistics")
async def admin_stats_handler(message: Message, db_session: AsyncSession, db_user: User):
    if not is_admin(db_user.tg_id):
        return

    users_count = await db_session.scalar(select(func.count(User.id)))
    keys_total  = await db_session.scalar(select(func.count(Key.id))) or 0
    keys_used   = await db_session.scalar(select(func.count(Key.id)).where(Key.is_used == True)) or 0
    keys_free   = keys_total - keys_used
    total_sales = await db_session.scalar(select(func.sum(Purchase.price))) or 0
    total_paid  = await db_session.scalar(select(func.sum(Payment.amount)).where(Payment.status == "approved")) or 0
    pending_cnt = await db_session.scalar(select(func.count(Payment.id)).where(Payment.status == "pending")) or 0

    text = (
        f"📊 <b>СТАТИСТИКА</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Пайдаланушылар: <b>{users_count}</b>\n\n"
        f"🔑 Кілттер барлығы: <b>{keys_total}</b>\n"
        f"   ✅ Пайдаланылған: {keys_used}\n"
        f"   🟡 Қалған:        {keys_free}\n\n"
        f"💰 Жалпы сатылым:     <b>{total_sales:,.0f} ₸</b>\n"
        f"💳 Бекітілген төлем:  <b>{total_paid:,.0f} ₸</b>\n"
        f"⏳ Күтіп тұрған:      <b>{pending_cnt}</b>"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "📦 Қойма мен Сатылым")
async def stock_and_sales_handler(message: Message, db_session: AsyncSession, db_user: User):
    if not is_admin(db_user.tg_id):
        return

    # 1. Қойма статистикасы (қанша кілт қалды)
    stock_query = (
        select(Product.name, func.count(Key.id))
        .outerjoin(Key, and_(Key.product_id == Product.id, Key.is_used == False))
        .group_by(Product.name)
    )
    stock_result = await db_session.execute(stock_query)
    stock_data = stock_result.all()

    # 2. Сатылым статистикасы (кім қандай кілттер алды)
    sales_query = (
        select(User.username, User.tg_id, Product.name, func.count(Key.id))
        .join(Key, Key.used_by == User.tg_id)
        .join(Product, Product.id == Key.product_id)
        .where(Key.is_used == True)
        .group_by(User.tg_id, User.username, Product.name)
        .order_by(func.count(Key.id).desc())
    )
    sales_result = await db_session.execute(sales_query)
    sales_data = sales_result.all()

    # Форматтау
    lines = ["<b>📦 ҚОЙМА СТАТИСТИКАСЫ:</b>\n"]
    for prod_name, count in stock_data:
        lines.append(f"• <b>{prod_name}</b>: {count} кілт бар")
    
    lines.append("\n<b>👥 ПАЙДАЛАНУШЫЛАР САТЫЛЫМЫ:</b>\n")
    
    if not sales_data:
        lines.append("Әзірге сатылым жоқ.")
    else:
        user_sales = {}
        for username, tg_id, product_name, count in sales_data:
            if tg_id not in user_sales:
                user_sales[tg_id] = {"username": username, "products": []}
            user_sales[tg_id]["products"].append(f"{product_name}: {count} дана")
            
        for tg_id, data in user_sales.items():
            uname = f"@{data['username']}" if data['username'] else "Жасырын"
            prods = ", ".join(data['products'])
            lines.append(f"🔹 {uname} (<code>{tg_id}</code>) — {prods}")

    # Бөлікке бөлу логикасы (4096 шектеуін айналып өту)
    MAX_LEN = 4000
    current_chunk = ""
    for line in lines:
        if len(current_chunk) + len(line) + 1 > MAX_LEN:
            await message.answer(current_chunk, parse_mode="HTML")
            current_chunk = line + "\n"
        else:
            current_chunk += line + "\n"
    
    if current_chunk.strip():
        await message.answer(current_chunk, parse_mode="HTML")
