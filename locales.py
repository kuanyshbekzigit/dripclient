# locales.py
from typing import Dict

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "en": {
        "welcome": "🚀 <b>WELCOME TO DRIP CLIENT!</b>\n━━━━━━━━━━━━━━━━━━━━\n\n🛡 Please verify your phone number to log in.\nTap the «📱 Share Contact» button below 👇",
        "share_contact": "📱 Share Contact",
        "contact_error": "⚠️ Error: Please share only your own number.",
        "verify_success": "✅ <b>Verified Successfully!</b>\n\n📱 Number: <code>{phone}</code>\n\n🔓 All bot features are now available!",
        "dashboard_title": "💎 <b>USER DASHBOARD</b> 💎",
        "stats": "📈 <b>YOUR STATISTICS:</b>",
        "balance": "💰 Balance",
        "spent": "🛍 Spent",
        "status": "🔮 Status",
        "status_active": "🟢 Active",
        "time": "⏱ Time",
        "btn_products": "🛒 Products (Catalog)",
        "btn_topup": "💳 Top-up Balance",
        "btn_keys": "🔑 My Keys",
        "btn_referral": "🎁 Bonuses (Referral)",
        "btn_profile": "👤 My Profile",
        "btn_links": "🌍 Useful Links",
        "btn_settings": "⚙️ Settings (Language)",
        "profile_title": "👤 <b>PROFILE INFO</b>",
        "joined": "📅 Registration Date",
        "ref_sys": "🎁 <b>BONUS SYSTEM</b>\n━━━━━━━━━━━━━━━━━━━━\n🤝 Invite friends and get benefits!\n\n🔗 Your personal link:\n<code>{link}</code>\n\n📊 <b>Results:</b>\n   👥 Invited people: <b>{count}</b>",
        "ref_bonus": "\n💎 Bonus balance: <b>{bonus:,.0f} ₸</b>",
        "links_title": "🌍 <b>USEFUL LINKS</b>",
        "topup_title": "💳 <b>TOP-UP BALANCE</b>\n━━━━━━━━━━━━━━━━━━━━\n\nHow much do you want to deposit? 💸\nEnter the amount in digits (e.g. 1000):",
        "invalid_amount": "⚠️ Error: Enter valid digits only.",
        "amount_zero": "⚠️ Error: Amount must be greater than 0.",
        "kaspi_pay": "💳 <b>KASPI PAYMENT</b>\n━━━━━━━━━━━━━━━━━━━━\n\n💸 Amount to pay: <b>{amount:,.0f} ₸</b>\n\n<blockquote><b>Каспий</b> 🏦\n\n<code>{phone}</code>\n<i>{receiver}</i> ✅</blockquote>\n\n✅ Make the payment and be sure to:\n📸 <i>Send the payment receipt (screenshot or pdf) here!</i>",
        "send_receipt": "⚠️ Error: Please send an image or file (receipt).",
        "payment_sent": "⏳ <b>Request received!</b>\n\nAdmin will check the receipt and top up your balance.\nPlease wait. 🙏",
        "products_empty": "🛒 <i>No products right now. Check back later.</i>",
        "products_title": "💎 <b>PREMIUM LICENSES</b> 💎\n━━━━━━━━━━━━━━━━━━━━\nSelect the desired duration:",
        "vip_price_active": "✨ <i>VIP discounts available for you!</i>",
        "buy_success": "🎉 <b>PURCHASE SUCCESSFUL!</b>\n\n{msg}\n\n💳 Remaining balance: <b>{balance:,.0f} ₸</b>",
        "keys_empty": "📭 You don't have any keys yet.\n\n🛒 Go to Catalog to make your first purchase!",
        "keys_title": "🔑 <b>MY KEYS</b>",
        "select_lang": "🌍 Тілді таңдаңыз / Выберите язык / Choose language:",
        "lang_changed": "✅ Language successfully changed!",
        "vip_already": "🌟 You are already a VIP! Discounts applied.",
        "vip_invalid": "🚫 Error: VIP code is invalid or already used.",
        "vip_activated": "🌟 <b>Congratulations!</b> VIP status activated successfully.\nSpecial prices are now available for all products!",
    }
}

def get_text(lang: str, key: str, **kwargs) -> str:
    lang = "en"
    text = TRANSLATIONS[lang].get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text

def get_all_translations(key: str) -> list[str]:
    return [TRANSLATIONS["en"].get(key, key)]
