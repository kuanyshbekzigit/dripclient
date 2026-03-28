from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import User, Payment
from config import config
from database.github_sync import save_database
import asyncio

router = Router()


class AdminPaymentState(StatesGroup):
    waiting_for_amount = State()


@router.callback_query(F.data.startswith("pay_approve_"))
async def approve_payment_cb(callback: CallbackQuery, db_session: AsyncSession, state: FSMContext):
    if callback.from_user.id not in config.admin_ids:
        await callback.answer("⛔ Рұқсат жоқ!", show_alert=True)
        return

    _, _, payment_id, user_tg_id = callback.data.split("_", 3)
    payment_id, user_tg_id = int(payment_id), int(user_tg_id)

    payment = await db_session.scalar(select(Payment).where(Payment.id == payment_id))
    if not payment:
        await callback.answer("Төлем табылмады.", show_alert=True)
        return
    if payment.status != "pending":
        await callback.answer(f"Төлем бұрын өңделді: {payment.status}", show_alert=True)
        return

    await state.set_state(AdminPaymentState.waiting_for_amount)
    await state.update_data(
        payment_id=payment_id,
        user_tg_id=user_tg_id,
        original_caption=callback.message.caption,
        message_id=callback.message.message_id,
        chat_id=callback.message.chat.id
    )
    
    await callback.message.answer(
        "✅ Түбіртек расталды. Бұл пайдаланушыға қанша теңге баланс қосу керек?\n"
        "<i>(Тек сандармен жазыңыз, мысалы: 5000)</i>",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminPaymentState.waiting_for_amount)
async def admin_payment_amount_entered(message: Message, db_session: AsyncSession, bot: Bot, state: FSMContext):
    if message.from_user.id not in config.admin_ids:
        return
        
    try:
        amount = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("❌ Қате! Тек санды жазыңыз.")
        return
        
    data = await state.get_data()
    payment_id = data["payment_id"]
    user_tg_id = data["user_tg_id"]
    
    payment = await db_session.scalar(select(Payment).where(Payment.id == payment_id))
    if not payment or payment.status != "pending":
        await state.clear()
        return
        
    user = await db_session.scalar(select(User).where(User.tg_id == user_tg_id))
    if not user:
        await message.answer("Пайдаланушы табылмады.")
        await state.clear()
        return

    payment.status = "approved"
    payment.amount = amount
    user.balance += amount
    await db_session.commit()
    asyncio.create_task(save_database())

    # Update admin message
    new_caption = (
        (data.get("original_caption") or "") + "\n\n"
        f"✅ <b>МАҚҰЛДАНДЫ ({amount:,.0f} ₸)</b> — @{message.from_user.username or message.from_user.id}"
    )
    try:
        await bot.edit_message_caption(
            chat_id=data["chat_id"],
            message_id=data["message_id"],
            caption=new_caption,
            reply_markup=None,
            parse_mode="HTML"
        )
    except Exception:
        pass
        
    await message.answer(f"✅ Пайдаланушының ({user_tg_id}) балансына {amount:,.0f} ₸ қосылды!")

    # Notify user
    try:
        await bot.send_message(
            chat_id=user_tg_id,
            text=(
                f"✅ <b>Төлем мақұлданды!</b>\n\n"
                f"💰 <b>{amount:,.0f} ₸</b> балансыңызға қосылды.\n"
                f"Жаңа баланс: <b>{user.balance:,.0f} ₸</b>"
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass

    await state.clear()


@router.callback_query(F.data.startswith("pay_reject_"))
async def reject_payment_cb(callback: CallbackQuery, db_session: AsyncSession, bot: Bot):
    if callback.from_user.id not in config.admin_ids:
        await callback.answer("⛔ Рұқсат жоқ!", show_alert=True)
        return

    _, _, payment_id, user_tg_id = callback.data.split("_", 3)
    payment_id, user_tg_id = int(payment_id), int(user_tg_id)

    payment = await db_session.scalar(select(Payment).where(Payment.id == payment_id))
    if not payment:
        await callback.answer("Төлем табылмады.", show_alert=True)
        return
    if payment.status != "pending":
        await callback.answer(f"Төлем бұрын өңделді: {payment.status}", show_alert=True)
        return

    payment.status = "rejected"
    await db_session.commit()

    new_caption = (
        callback.message.caption + "\n\n"
        f"❌ <b>ҚАБЫЛДАНБАДЫ</b> — @{callback.from_user.username or callback.from_user.id}"
    )
    await callback.message.edit_caption(caption=new_caption, reply_markup=None, parse_mode="HTML")

    try:
        await bot.send_message(
            chat_id=user_tg_id,
            text=(
                f"❌ <b>Төлеміңіз қабылданбады.</b>\n\n"
                f"Сома: <b>{payment.amount:,.0f} ₸</b>\n\n"
                f"Сұрақ болса, админге хабарласыңыз."
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass

    await callback.answer("❌ Қабылданбады!")
