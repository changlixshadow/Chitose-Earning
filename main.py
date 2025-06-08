import os
import json
import random
import string
import time
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ContextTypes, ConversationHandler
)
from telegram.constants import ParseMode

# --- CONFIG ---
TOKEN = "8006836827:AAERFD1tDpBDJhvKm_AHy20uSAzZdoRwbZc"
ADMIN_ID = 5759232282

START_IMAGE = "https://telegra.ph/file/050a20dace942a60220c0-6afbc023e43fad29c7.jpg"
ABOUT_IMAGE = "https://telegra.ph/file/9d18345731db88fff4f8c-d2b3920631195c5747.jpg"
HELP_IMAGE = "https://telegra.ph/file/e6ec31fc792d072da2b7e-54e7c7d4c5651823b3.jpg"

USERS_FILE = "users.json"
CODES_FILE = "codes.json"
SHORTENER_LINKS_FILE = "shorteners.json"

ASK_UPI = range(1)

# LinkCents API info
LINKCENTS_API_KEY = "a3dede8bbc12f4bd0afd61cf1ac691f3545d5faf"
BASE_EARN_URL = "https://yourdestinationlink.com"  # <-- Replace with your earning link


# --- JSON UTILS ---
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)


# --- USER DATA ---
def get_user(user_id: int):
    users = load_json(USERS_FILE)
    uid = str(user_id)
    if uid not in users:
        users[uid] = {
            "balance": 0.0,
            "used_codes": [],
            "upi": None,
            "referrals": [],
            "refer_by": None
        }
        save_json(USERS_FILE, users)
    return users[uid]

def update_user(user_id: int, data: dict):
    users = load_json(USERS_FILE)
    users[str(user_id)] = data
    save_json(USERS_FILE, users)

def add_balance(user_id: int, amount: float):
    user = get_user(user_id)
    user["balance"] += amount
    update_user(user_id, user)


# --- CODES DATA ---
def is_code_used(code: str) -> bool:
    codes = load_json(CODES_FILE)
    return code in codes

def add_code(code: str):
    codes = load_json(CODES_FILE)
    codes[code] = True
    save_json(CODES_FILE, codes)


# --- SHORT LINK GENERATION ---
def generate_alias(length=6):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def generate_short_link(user_id: int):
    alias = generate_alias()
    url_with_ref = f"{BASE_EARN_URL}?ref={user_id}"
    short_link = (
        f"https://linkcents.com/api?api={LINKCENTS_API_KEY}"
        f"&url={url_with_ref}"
        f"&alias={alias}"
    )

    # Save shortener details in JSON
    shortener_links = load_json(SHORTENER_LINKS_FILE)
    shortener_links[alias] = {
        "user_id": user_id,
        "original_url": url_with_ref,
        "short_link": short_link,
        "timestamp": int(time.time())
    }
    save_json(SHORTENER_LINKS_FILE, shortener_links)

    return short_link


# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args

    # Handle referral on start
    if args:
        referrer = args[0]
        if referrer != str(user_id):
            user = get_user(user_id)
            if user["refer_by"] is None:
                user["refer_by"] = referrer
                update_user(user_id, user)

                # Give referral bonus
                ref_user = get_user(int(referrer))
                ref_user["balance"] += 0.02
                ref_user["referrals"].append(user_id)
                update_user(int(referrer), ref_user)

    buttons = [
        [InlineKeyboardButton("📢 About", callback_data="about"),
         InlineKeyboardButton("🆘 Help", callback_data="help")],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ]
    text = (
        "<b>🎉 Welcome to the Earning Bot!</b>\n\n"
        "Earn money by visiting short links and submitting codes.\n"
        "💰 Use /shortener to get your earning link.\n"
        "💼 Use /balance to check your earnings.\n"
        "🏦 Use /withdraw to cash out.\n"
        "👥 Use /refer to share your referral link and earn ₹0.02 per referral!"
    )
    await update.message.reply_photo(
        photo=START_IMAGE,
        caption=text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    back_buttons = [
        [InlineKeyboardButton("🔙 Back", callback_data="start"),
         InlineKeyboardButton("❌ Close", callback_data="close")]
    ]

    if data == "close":
        await query.message.delete()
        return
    elif data == "start":
        buttons = [
            [InlineKeyboardButton("📢 About", callback_data="about"),
             InlineKeyboardButton("🆘 Help", callback_data="help")],
            [InlineKeyboardButton("❌ Close", callback_data="close")]
        ]
        text = (
            "<b>🎉 Welcome to the Earning Bot!</b>\n\n"
            "Earn money by visiting short links and submitting codes.\n"
            "💰 Use /shortener to get your earning link.\n"
            "💼 Use /balance to check your earnings.\n"
            "🏦 Use /withdraw to cash out.\n"
            "👥 Use /refer to share your referral link and earn ₹0.02 per referral!"
        )
        await query.message.edit_media(
            media=InputMediaPhoto(START_IMAGE),
            caption=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
    elif data == "about":
        about_text = (
            "<b>📢 About This Bot</b>\n"
            "We are a rewards-based platform where you earn money by completing short tasks like visiting shortened links.\n\n"
            "💹 Invite your friends and start earning now!\n"
            "Join our community and support our channels."
        )
        await query.message.edit_media(
            media=InputMediaPhoto(ABOUT_IMAGE, caption=about_text, parse_mode=ParseMode.HTML),
            reply_markup=InlineKeyboardMarkup(back_buttons)
        )
    elif data == "help":
        help_text = (
            "<b>🆘 Help Section</b>\n\n"
            "📌 Use /shortener to get your paid link.\n"
            "✅ After opening the link, you'll receive a code.\n"
            "💬 Send that code here to earn ₹0.01 instantly.\n"
            "🏦 Use /withdraw to get your balance via UPI.\n"
            "📊 Use /balance to see your total earnings.\n\n"
            "Happy earning!"
        )
        await query.message.edit_media(
            media=InputMediaPhoto(HELP_IMAGE, caption=help_text, parse_mode=ParseMode.HTML),
            reply_markup=InlineKeyboardMarkup(back_buttons)
        )
    else:
        await query.answer("Unknown action!")


async def shortener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    short_link = generate_short_link(user_id)
    user["last_link"] = short_link
    update_user(user_id, user)

    await update.message.reply_text(f"🔗 Your earning short link:\n{short_link}")


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    await update.message.reply_text(f"💰 Your balance is ₹{user['balance']:.2f}")


async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    referral_count = len(user["referrals"])
    username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{username}?start={user_id}"
    text = (
        f"👥 You have referred <b>{referral_count}</b> user(s).\n"
        f"Share your referral link and earn ₹0.02 per referral!\n\n"
        f"🔗 <b>Your referral link:</b>\n{referral_link}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    bal = user["balance"]

    if bal < 1 or bal > 10:
        await update.message.reply_text("❌ You can withdraw only between ₹1 and ₹10.")
        return ConversationHandler.END

    await update.message.reply_text(f"📥 Please enter your UPI ID to receive ₹{bal:.2f}:")
    return ASK_UPI


async def receive_upi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    upi_id = update.message.text.strip()

    user = get_user(user_id)
    bal = user["balance"]

    user["upi"] = upi_id
    user["balance"] = 0.0
    update_user(user_id, user)

    # Notify admin
    await context.bot.send_message(
        ADMIN_ID,
        f"🧾 <b>Withdraw Request</b>\n"
        f"👤 User ID: {user_id}\n"
        f"💵 Amount: ₹{bal:.2f}\n"
        f"🏦 UPI ID: {upi_id}",
        parse_mode=ParseMode.HTML
    )

    await update.message.reply_text("✅ Withdraw request received. Payment will be made within 24 hours.")
    return ConversationHandler.END


async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    user_id = update.effective_user.id
    user = get_user(user_id)

    if is_code_used(code):
        await update.message.reply_text("❌ This code has already been used.")
        return

    add_code(code)
    user["balance"] += 0.01
    user["used_codes"].append(code)
    update_user(user_id, user)

    await update.message.reply_text("✅ Code accepted! You earned ₹0.01.")


async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    users = load_json(USERS_FILE)
    total_users = len(users)
    sorted_users = sorted(users.items(), key=lambda x: x[1]["balance"], reverse=True)
    top5 = sorted_users[:5]

    text = f"👥 Total users: <b>{total_users}</b>\n\n<b>Top 5 Users by Balance:</b>\n"
    for i, (uid, data) in enumerate(top5, 1):
        text += f"{i}. User ID: <code>{uid}</code> - ₹{data['balance']:.2f}\n"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# --- Conversation ---
withdraw_conv = ConversationHandler(
    entry_points=[CommandHandler("withdraw", withdraw)],
    states={ASK_UPI: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_upi)]},
    fallbacks=[]
)


# --- Register all handlers ---
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(CommandHandler("shortener", shortener))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("refer", refer))
    app.add_handler(CommandHandler("users", users))
    app.add_handler(withdraw_conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_code))

    print("Bot started!")
    app.run_polling()


if __name__ == "__main__":
    main()
