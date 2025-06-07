import os
import json
import random
from flask import Flask, request
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ContextTypes, ConversationHandler
)
from telegram.constants import ParseMode

# --- CONFIGURATION ---
TOKEN = "8006836827:AAERFD1tDpBDJhvKm_AHy20uSAzZdoRwbZc"
ADMIN_ID = 5759232282

START_IMAGE = "https://telegra.ph/file/050a20dace942a60220c0-6afbc023e43fad29c7.jpg"
ABOUT_IMAGE = "https://telegra.ph/file/9d18345731db88fff4f8c-d2b3920631195c5747.jpg"
HELP_IMAGE = "https://telegra.ph/file/e6ec31fc792d072da2b7e-54e7c7d4c5651823b3.jpg"

USERS_FILE = "users.json"
CODES_FILE = "codes.json"
SHORTENERS_FILE = "shorteners.json"

ASK_UPI = range(1)

# --- FLASK APP & TELEGRAM BOT INIT ---
app = Flask(__name__)
bot_app = Application.builder().token(TOKEN).build()

# --- JSON FILE HANDLING ---
def load_json(file):
    return json.load(open(file)) if os.path.exists(file) else {}

def save_json(file, data):
    json.dump(data, open(file, "w"), indent=2)

# --- USER MANAGEMENT ---
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

# --- CODE MANAGEMENT ---
def add_code(code):
    codes = load_json(CODES_FILE)
    codes[code] = "used"
    save_json(CODES_FILE, codes)

def is_code_used(code):
    codes = load_json(CODES_FILE)
    return code in codes

# --- SHORTENER ---
def get_random_shortener():
    shorteners = load_json(SHORTENERS_FILE)
    return random.choice(shorteners) if shorteners else None

# --- START COMMAND ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [InlineKeyboardButton("📢 About", callback_data="about"),
         InlineKeyboardButton("🆘 Help", callback_data="help")],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ]
    await update.message.reply_photo(
        photo=START_IMAGE,
        caption="<b>🎉 Welcome to Earning Bot!</b>\nEarn money by visiting short links and submitting codes.\n💰 Use /shortener to begin!\n💼 Use /balance to check earnings.\n🏦 Use /withdraw to cash out.",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )

# --- INLINE BUTTON HANDLER ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "close":
        await query.message.delete()
    elif query.data == "about":
        await query.message.edit_media(
            media=InputMediaPhoto(ABOUT_IMAGE, caption="""
<b>📢 About This Bot</b>
We are a rewards-based platform where you can earn money by completing short tasks like visiting shortened links.

💹 Invite your friends and start earning now!
Join our community and support our channels.
""", parse_mode=ParseMode.HTML)
        )
    elif query.data == "help":
        await query.message.edit_media(
            media=InputMediaPhoto(HELP_IMAGE, caption="""
<b>🆘 Help Section</b>

📌 Use /shortener to get your paid link.
✅ After opening the link, you'll receive a code.
💬 Send that code here to earn ₹0.01 instantly.
🏦 Use /withdraw to get your balance via UPI.
📊 Use /balance to see your total earnings.

Happy earning!
""", parse_mode=ParseMode.HTML)
        )

# --- SHORTENER COMMAND ---
async def shortener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_user(user_id)
    shortener = get_random_shortener()

    if not shortener:
        await update.message.reply_text("⚠️ No shortener available.")
        return

    code = str(random.randint(100000, 999999))
    link = f"{shortener['api_url']}{code}"
    add_code(code)
    user_data['last_link'] = link
    update_user(user_id, user_data)

    if user_id == ADMIN_ID:
        await update.message.reply_text(f"🔗 Link: {link}\n🔐 Code: {code}")
    else:
        await update.message.reply_text(f"🔗 Your earning link:\n{link}")

# --- BALANCE CHECK ---
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_user(user_id)
    await update.message.reply_text(f"💰 Your balance is ₹{user_data['balance']:.2f}")

# --- WITHDRAW COMMAND ---
async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_user(user_id)

    if 1 <= user_data['balance'] <= 10:
        await update.message.reply_text("📥 Please enter your UPI ID for receiving ₹{:.2f}".format(user_data['balance']))
        return ASK_UPI
    else:
        await update.message.reply_text("❌ Withdrawable balance must be between ₹1 and ₹10.")
        return ConversationHandler.END

# --- RECEIVE UPI ID ---
async def receive_upi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    upi = update.message.text.strip()
    user_data = get_user(user_id)

    user_data['upi'] = upi
    amount = user_data['balance']

    # Notify admin
    await context.bot.send_message(
        ADMIN_ID,
        f"🧾 <b>Withdraw Request</b>\n👤 User ID: {user_id}\n💵 Amount: ₹{amount:.2f}\n🏦 UPI: {upi}",
        parse_mode=ParseMode.HTML
    )

    # Confirm to user
    await update.message.reply_text("✅ Request received. Payment will be made within 24h.")
    user_data['balance'] = 0
    update_user(user_id, user_data)
    return ConversationHandler.END

# --- HANDLE TEXT CODE SUBMISSION ---
async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    user_id = update.effective_user.id
    user_data = get_user(user_id)

    if is_code_used(code):
        await update.message.reply_text("❌ This code is already used.")
        return

    add_code(code)
    user_data['balance'] += 0.01
    user_data['used_codes'].append(code)
    update_user(user_id, user_data)
    await update.message.reply_text("✅ Code accepted. You earned ₹0.01!")

# --- BOT SETUP ---
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CallbackQueryHandler(callback_handler))
bot_app.add_handler(CommandHandler("shortener", shortener))
bot_app.add_handler(CommandHandler("balance", balance))

# Withdraw conversation
withdraw_conv = ConversationHandler(
    entry_points=[CommandHandler("withdraw", withdraw)],
    states={ASK_UPI: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_upi)]},
    fallbacks=[]
)
bot_app.add_handler(withdraw_conv)

# Code input (any plain text)
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_code))

# --- FLASK ROUTES ---
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot_app.bot)
    bot_app.update_queue.put(update)
    return "ok"

@app.route("/")
def index():
    return "Bot is live!"

# --- MAIN RUN ---
if __name__ == '__main__':
    bot_app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        url_path=TOKEN,
        webhook_url=f"https://your-render-url.onrender.com/{TOKEN}"  # Replace with your Render URL
    )
