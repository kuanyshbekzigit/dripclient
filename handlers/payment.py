from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, Payment
from config import config
from keyboards.admin_kb import approve_reject_keyboard
from keyboards.user_kb import main_inline_keyboard, back_to_main_keyboard
from locales import get_text, get_all_translations

router = Router()


class PaymentState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_receipt = State()


@router.callback_query(F.data == "menu_topup")
async def topup_cb_handler(callback: CallbackQuery, state: FSMContext, db_user: User):
    await state.set_state(PaymentState.waiting_for_receipt)
    await state.update_data(amount=0.0)
    
    text = (
        "💳 <b>Please transfer the required amount to the approved Kaspi details:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<blockquote>🏦 <b>Kaspi Bank</b>\n"
        f"📞 <code>{config.kaspi_phone}</code>\n"
        f"👤 {config.kaspi_receiver} ✅</blockquote>\n\n"
        "<i>📸 After payment, please send the receipt (photo or PDF) exactly here:</i> 👇"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=back_to_main_keyboard(db_user.language)
    )
    await callback.answer()


@router.message(PaymentState.waiting_for_receipt, F.photo | F.document)
async def payment_receipt_handler(
    message: Message, state: FSMContext, bot: Bot,
    db_user: User, db_session: AsyncSession
):
    data = await state.get_data()
    amount = data.get("amount")

    file_id = None
    is_photo = False
    if message.photo:
        file_id = message.photo[-1].file_id
        is_photo = True
    elif message.document:
        file_id = message.document.file_id

    if not file_id:
        await message.answer(get_text(db_user.language, "send_receipt"))
        return

    payment = Payment(
        user_tg_id=db_user.tg_id,
        amount=amount,
        receipt_file_id=file_id,
        status="pending"
    )
    db_session.add(payment)
    await db_session.commit()
    await db_session.refresh(payment)

    await state.clear()
    await message.answer(
        get_text(db_user.language, "payment_sent"),
        parse_mode="HTML",
        reply_markup=main_inline_keyboard(db_user.language)
    )

    if not config.admin_ids:
        return

    admin_text = (
        f"📥 <b>ЖАҢА ТӨЛЕМ СҰРАНЫСЫ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 User: @{message.from_user.username or 'no_username'}\n"
        f"🆔 Telegram ID: <code>{db_user.tg_id}</code>\n"
        f"🔢 Төлем ID: #{payment.id}\n\n"
        f"⚠️ <i>Түбіртекті тексеріп, сомасын енгізіңіз.</i>"
    )

    kb = approve_reject_keyboard(payment.id, db_user.tg_id)

    for admin_id in config.admin_ids:
        try:
            if is_photo:
                await bot.send_photo(
                    chat_id=admin_id,
                    photo=file_id,
                    caption=admin_text,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
            else:
                await bot.send_document(
                    chat_id=admin_id,
                    document=file_id,
                    caption=admin_text,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
        except Exception as e:
            print(f"Admin {admin_id} хабар жіберілмеді: {e}")

