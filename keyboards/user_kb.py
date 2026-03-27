from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from locales import get_text

# ─── CONTACT SHARE (first-time users) ────────────────────────────

def share_contact_keyboard(lang: str = "kk") -> ReplyKeyboardMarkup:
    """Keyboard with a request_contact button for identity verification."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=get_text(lang, "share_contact"), request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


# ─── USER KEYBOARDS ───────────────────────────────────────────────

def main_inline_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Main dashboard inline keyboard with API 9.4 styles."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=get_text(lang, "btn_products"), callback_data="menu_products", **{"style": "primary"}),
                InlineKeyboardButton(text=get_text(lang, "btn_topup"), callback_data="menu_topup", **{"style": "success"})
            ],
            [
                InlineKeyboardButton(text=get_text(lang, "btn_keys"), callback_data="menu_keys", **{"style": "primary"}),
                InlineKeyboardButton(text=get_text(lang, "btn_referral"), callback_data="menu_referral", **{"style": "primary"})
            ],
            [
                InlineKeyboardButton(text=get_text(lang, "btn_profile"), callback_data="menu_profile"),
                InlineKeyboardButton(text=get_text(lang, "btn_links"), callback_data="menu_links")
            ]
        ]
    )

def back_to_main_keyboard(lang: str = "en", text: str = "⬅️ Артқа / Back") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data="back_to_main", **{"style": "danger"})]
        ]
    )


def products_keyboard(products, is_vip: bool = False, lang: str = "kk") -> InlineKeyboardMarkup:
    """Buttons in a grid (2 per row) matching the user's screenshot."""
    rows = []
    current_row = []
    for p in products:
        label = f"🔑 {p.name}"
        current_row.append(
            InlineKeyboardButton(
                text=label,
                callback_data=f"buy_{p.id}"
            )
        )
        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []
    
    if current_row:
        rows.append(current_row)
        
    # Add back button at the bottom
    rows.append([InlineKeyboardButton(text="⬅️ Артқа / Back", callback_data="back_to_main", **{"style": "danger"})])

    return InlineKeyboardMarkup(inline_keyboard=rows)
