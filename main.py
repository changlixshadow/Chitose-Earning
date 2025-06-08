import os
import json
import random
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ContextTypes, ConversationHandler
)
from telegram.constants import ParseMode

TOKEN = "8006836827:AAERFD1tDpBDJhvKm_AHy20uSAzZdoRwbZc"
ADMIN_ID = 5759232282

START_IMAGE = "https://telegra.ph/file/050a20dace942a60220c0-6afbc023e43fad29c7.jpg"
ABOUT_IMAGE = "https://telegra.ph/file/9d18345731db88fff4f8c-d2b3920631195c5747.jpg"
HELP_IMAGE = "https://telegra.ph/file/e6ec31fc792d072da2b7e-54e7c7d4c5651823b3.jpg"

ASK_UPI = range(1)

USERS_FILE = "users.json"
CODES_FILE = "codes.json"

LINKCENT_API_KEY = "a3dede8bbc12f4bd0afd61cf1ac691f3545d5faf"
LINKCENT_BASE_URL = "https://linkcents.com/api?api_key=" + LINKCENT_API_KEY + "&url="

def load_json(file):
    return json.load(open(file)) if os.path.exists(file) else {}

def save_json(file, data):
    json.dump(data, open(file, "w"), indent=2)

def get_user(user_id):
    users = load_json(USERS_FILE)
    if str(user_id) not in users:
        users[str(user_id)] = {"balance": 0.0, "used_codes": [], "upi": None}
        save_json(USERS_FILE, users)
    return users[str(user_id)]

def update_user(user_id, user_data):
    users = load_json(USERS_FILE)
    users[str(user_id)] = user_data
    save_json(USERS_FILE, users)

def add_code(code):
    codes = load_json(CODES_FILE)
    codes[code] = "used"
    save_json(CODES_FILE, codes)

def is_code_used(code):
    codes = load_json(CODES_FILE)
    return code in codes

# --- BUTTONS ---

def main_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 About", callback_data="about"),
         InlineKeyboardButton("🆘 Help", callback_data="help")],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ])

def about_help_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="back"),
         InlineKeyboardButton("📢 About", callback_data="about")],
        [InlineKeyboardButton("🆘 Help", callback_data="help"),
         InlineKeyboardButton("❌ Close", callback_data="close")]
    ])

# --- START ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_photo(
        photo=START_IMAGE,
        caption="<b>🎉 Welcome to Earning Bot!</b>\nEarn money by visiting short links and submitting codes.\n\n💰 Use /shortener to begin!\n💼 Use /balance to check earnings.\n🏦 Use /withdraw to cash out.",
        reply_markup=main_buttons(),
        parse_mode=ParseMode.HTML
    )

# --- CALLBACK QUERY HANDLER ---

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "close":
        await query.message.delete()
    elif query.data == "back":
        # Show main start buttons with start image & caption
        await query.message.edit_media(
            media=InputMediaPhoto(START_IMAGE),
            reply_markup=main_buttons(),
            caption="<b>🎉 Welcome back!</b>\nEarn money by visiting short links and submitting codes.\n\n💰 Use /shortener to begin!\n💼 Use /balance to check earnings.\n🏦 Use /withdraw to cash out.",
            parse_mode=ParseMode.HTML
        )
    elif query.data == "about":
        await query.message.edit_media(
            media=InputMediaPhoto(ABOUT_IMAGE),
            caption=(
                "<b>📢 About This Bot</b>\n"
                "Earn money by completing short tasks like visiting shortened links.\n"
                "Invite friends and support our channels.\n\n"
                "<i>Use the buttons below to navigate.</i>"
            ),
            reply_markup=about_help_buttons(),
            parse_mode=ParseMode.HTML
        )
    elif query.data == "help":
        await query.message.edit_media(
            media=InputMediaPhoto(HELP_IMAGE),
            caption=(
                "<b>🆘 Help Section</b>\n\n"
                "• Use /shortener to get your paid link.\n"
                "• After opening the link, you get a code.\n"
                "• Send that code here to earn ₹0.01 instantly.\n"
                "• Use /withdraw to cash out.\n"
                "• Use /balance to check your earnings.\n\n"
                "Happy earning!"
            ),
            reply_markup=about_help_buttons(),
            parse_mode=ParseMode.HTML
        )

# --- SHORTENER COMMAND ---

async def shortener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_user(user_id)

    # Use a fixed long URL here, or get from user input
    long_url = "https://example.com/earn-money"  # You can customize this

    # Generate LinkCent short link
    import requests
    try:
        api_url = f"{LINKCENT_BASE_URL}{long_url}"
        resp = requests.get(api_url, timeout=10)
        resp_json = resp.json()
        if resp.status_code == 200 and 'shorturl' in resp_json:
            short_url = resp_json['shorturl']
        else:
            short_url = None
    except Exception as e:
        short_url = None

    if not short_url:
        await update.message.reply_text("⚠️ Sorry, could not generate short link right now. Try again later.")
        return

    # Generate a random 6-digit code for user
    code = str(random.randint(100000, 999999))

    # Save the code to prevent reuse
    if not is_code_used(code):
        add_code(code)

    # Save user last code, last link if needed
    user_data['last_code'] = code
    user_data['last_link'] = short_url
    update_user(user_id, user_data)

    if user_id == ADMIN_ID:
        await update.message.reply_text(f"🔗 Short Link: {short_url}\n🔑 Your code: {code}")
    else:
        await update.message.reply_text(
            f"🔗 Here is your earning link:\n{short_url}\n\n"
            f"📝 After visiting, send me the code to earn ₹0.01.\n"
            f"Your code: <b>{code}</b>",
            parse_mode=ParseMode.HTML
        )

# --- BALANCE COMMAND ---

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_user(user_id)
    await update.message.reply_text(f"💰 Your current balance is ₹{user_data['balance']:.2f}")

# --- WITHDRAW CONVERSATION ---

async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_user(user_id)
    bal = user_data.get("balance", 0.0)

    if bal < 1 or bal > 10:
        await update.message.reply_text("❌ Withdrawable balance must be between ₹1 and ₹10.")
        return ConversationHandler.END

    await update.message.reply_text(f"Please enter your UPI ID to withdraw ₹{bal:.2f}:")
    return ASK_UPI

async def receive_upi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    upi = update.message.text.strip()

    user_data = get_user(user_id)
    bal = user_data.get("balance", 0.0)

    # Send withdrawal request to admin
    await context.bot.send_message(
        ADMIN_ID,
        f"🧾 <b>Withdraw Request</b>\nUser ID: {user_id}\nAmount: ₹{bal:.2f}\nUPI: {upi}",
        parse_mode=ParseMode.HTML
    )

    await update.message.reply_text("✅ Withdrawal request received! Payment will be processed within 24 hours.")
    # Reset user balance
    user_data['balance'] = 0.0
    update_user(user_id, user_data)
    return ConversationHandler.END

# --- HANDLE CODE SUBMISSION ---

async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    user_id = update.effective_user.id
    user_data = get_user(user_id)

    if is_code_used(code):
        await update.message.reply_text("❌ This code has already been used.")
        return

    add_code(code)
    user_data['balance'] += 0.01
    user_data['used_codes'].append(code)
    update_user(user_id, user_data)
    await update.message.reply_text("✅ Code accepted! You earned ₹0.01.")

# --- MAIN ---

if __name__ == "__main__":
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(CommandHandler("shortener", shortener))
    app.add_handler(CommandHandler("balance", balance))

    withdraw_conv = ConversationHandler(
        entry_points=[CommandHandler("withdraw", withdraw)],
        states={ASK_UPI: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_upi)]},
        fallbacks=[]
    )
    app.add_handler(withdraw_conv)

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_code))

    print("Bot started with polling...")
    app.run_polling()
