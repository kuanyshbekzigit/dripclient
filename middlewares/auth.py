from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from database.crud import get_or_create_user
from database.engine import async_session
from config import config

class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user = None
        if isinstance(event, (Message, CallbackQuery)):
            user = event.from_user

        if user:
            async with async_session() as session:
                db_user = await get_or_create_user(session, user.id, user.username)

                is_admin = user.id in config.admin_ids
                if not is_admin:
                    if db_user.username and db_user.username in config.admin_usernames:
                        config.admin_ids.append(user.id)
                        is_admin = True
                    elif db_user.phone_number and db_user.phone_number in config.admin_phones:
                        config.admin_ids.append(user.id)
                        is_admin = True
                
                # Admins always pass through
                if is_admin:
                    data['db_session'] = session
                    data['db_user'] = db_user
                    return await handler(event, data)

                # Check if banned
                if db_user.is_banned:
                    if isinstance(event, Message):
                        await event.answer("⛔ Сіз блокталдыңыз.")
                    elif isinstance(event, CallbackQuery):
                        await event.answer("⛔ Сіз блокталдыңыз.", show_alert=True)
                    return None

                # Phone verification gate
                if not db_user.phone_number:
                    if isinstance(event, Message):
                        is_start = event.text and (event.text.startswith("/start") or event.text.startswith("/debug"))
                        is_contact = event.contact is not None
                        if not (is_start or is_contact):
                            from keyboards.user_kb import share_contact_keyboard
                            await event.answer(
                                f"⚠️ DEBUG_BLOCK_MSG:\nphone_number evaluates to: '{db_user.phone_number}'\ntext was: '{getattr(event, 'text', '')}'\nБотты қолдану үшін алдымен телефон нөміріңізді жіберіңіз.",
                                reply_markup=share_contact_keyboard()
                            )
                            return None
                    elif isinstance(event, CallbackQuery):
                        if event.data and event.data.startswith("lang_"):
                            # Allow language selection even without phone number
                            pass
                        else:
                            from keyboards.user_kb import share_contact_keyboard
                            await event.message.answer(
                                f"⚠️ DEBUG_BLOCK_CB:\nphone_number evaluates to: '{db_user.phone_number}'\nБотты қолдану үшін алдымен телефон нөміріңізді жіберіңіз.",
                                reply_markup=share_contact_keyboard()
                            )
                            await event.answer()
                            return None

                data['db_session'] = session
                data['db_user'] = db_user
                return await handler(event, data)

        return await handler(event, data)
