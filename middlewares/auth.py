from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from database.crud import get_or_create_user
from database.engine import async_session
from config import config

verified_users_cache = {}

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
                await session.refresh(db_user)

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
                # Check memory cache first
                if user.id in verified_users_cache and not db_user.phone_number:
                    db_user.phone_number = verified_users_cache[user.id]
                    await session.commit()

                if not db_user.phone_number:
                    if isinstance(event, Message):
                        is_start = event.text and (event.text.startswith("/start") or event.text.startswith("/debug"))
                        is_contact = event.contact is not None
                        if not (is_start or is_contact):
                            from keyboards.user_kb import share_contact_keyboard
                            await event.answer(
                                "⚠️ Please share your contact to use the bot.",
                                reply_markup=share_contact_keyboard()
                            )
                            return None
                    elif isinstance(event, CallbackQuery):
                        from keyboards.user_kb import share_contact_keyboard
                        await event.message.answer(
                            "⚠️ Please share your contact to use the bot.",
                            reply_markup=share_contact_keyboard()
                        )
                        await event.answer()
                        return None

                data['db_session'] = session
                data['db_user'] = db_user
                return await handler(event, data)

        return await handler(event, data)
