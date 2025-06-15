from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes
)
import json
import os
import random
import string
import datetime
import asyncio

BOT_TOKEN = "8006836827:AAERFD1tDpBDJhvKm_AHy20uSAzZdoRwbZc"
ADMIN_ID = 5759232282
GROUP_ID = "@gameshubreal"

# File names
USERS_FILE = "users.json"
CODES_FILE = "codes.json"
SHORTENERS_FILE = "shorteners.json"
WITHDRAWALS_FILE = "withdrawals.json"

# Utility functions to load and save JSON data
def load_json(filename):
    if not os.path.exists(filename) or os.path.getsize(filename) == 0:
        return {}
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# Initialize files if not exist
for file in [USERS_FILE, CODES_FILE, SHORTENERS_FILE, WITHDRAWALS_FILE]:
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump({}, f)

# Sample shortener config (You can add more shorteners here)
shorteners = {
    "linkcents": {
        "api_key": "a3dede8bbc12f4bd0afd61cf1ac691f3545d5faf",
        "base_url": "https://linkcents.com",
        "daily_limit_per_user": 10
    }
}
save_json(SHORTENERS_FILE, shorteners)


# /start command with referral
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users = load_json(USERS_FILE)
    user_id = str(user.id)

    if user_id not in users:
        # Handle referral if any
        referred_by = None
        if context.args:
            referred_by = context.args[0]
            if referred_by not in users:
                referred_by = None

        users[user_id] = {
            "balance": 0.0,
            "referrals": [],
            "referred_by": referred_by,
            "daily_shorteners_done": 0,
            "last_shortener_time": None,
            "codes_claimed": [],
            "last_withdraw_time": None
        }

        # Add to referrer's referrals list
        if referred_by:
            users[referred_by].setdefault("referrals", []).append(user_id)

        save_json(USERS_FILE, users)

    start_text = (
        "<b>Welcome to Shortener Bot v1.1</b>\n\n"
        "Earn money by completing shortener tasks.\n\n"
        "Commands:\n"
        "/shortener - Get shortener URL and earn\n"
        "/balance - Check your earnings\n"
        "/withdraw - Withdraw your balance\n"
        "/refer - Get your referral link\n\n"
        "Admin commands are restricted.\n\n"
        "Version 1.1 - More features coming soon!"
    )

    keyboard = [
        [
            InlineKeyboardButton("About", callback_data="about"),
            InlineKeyboardButton("Help", callback_data="help")
        ],
        [InlineKeyboardButton("Close", callback_data="close_start")]
    ]

    await update.message.reply_photo(
        photo="https://telegra.ph/file/050a20dace942a60220c0-6afbc023e43fad29c7.jpg",
        caption=start_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# Callback for closing the start/about/help messages
async def close_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()


# Callback for About button
async def about_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    about_text = (
        "<b>About Shortener Bot</b>\n\n"
        "This bot helps you earn money by completing shortener tasks.\n"
        "You get paid for each successful completion and can withdraw your balance.\n\n"
        "Refer friends and earn more!\n"
        "Version 1.1"
    )
    keyboard = [
        [
            InlineKeyboardButton("Back", callback_data="back_to_start"),
            InlineKeyboardButton("Help", callback_data="help")
        ],
        [InlineKeyboardButton("Close", callback_data="close_start")]
    ]
    # CORRECTED: कैप्शन और parse_mode को सीधे InputMediaPhoto में पास करें
    await query.edit_message_media(
        media=telegram.InputMediaPhoto(
            "https://telegra.ph/file/9d18345731db88fff4f8c-d2b3920631195c5747.jpg",
            caption=about_text,
            parse_mode="HTML"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    # यह लाइन (और पिछली 3 लाइनें) पहले यहाँ थीं, उन्हें अब पूरी तरह से हटा दिया गया है।
    # कृपया सुनिश्चित करें कि यह आपके कोड में नहीं है।


# Callback for Help button
async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    help_text = (
        "<b>Help - How to use Shortener Bot</b>\n\n"
        "/start - Register yourself\n"
        "/shortener - Get shortener link to earn\n"
        "/verify &lt;code&gt; - Verify code after completing shortener\n" # FIX: '<code>' को '&lt;code&gt;' में बदला
        "/balance - Check your earnings\n"
        "/withdraw <code>&lt;amount&gt;</code> <code>&lt;UPI_ID&gt;</code> - Withdraw money\n"
        "/refer - Get your referral link\n\n"
        "If you have any issues, contact the admin."
    )
    keyboard = [
        [
            InlineKeyboardButton("Back", callback_data="back_to_start"),
            InlineKeyboardButton("About", callback_data="about")
        ],
        [InlineKeyboardButton("Close", callback_data="close_start")]
    ]
    # CORRECTED: कैप्शन और parse_mode को सीधे InputMediaPhoto में पास करें
    await query.edit_message_media(
        media=telegram.InputMediaPhoto(
            "https://telegra.ph/file/e6ec31fc792d072da2b7e-54e7c7d4c5651823b3.jpg",
            caption=help_text,
            parse_mode="HTML"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    # यह लाइन (और पिछली 3 लाइनें) पहले यहाँ थीं, उन्हें अब पूरी तरह से हटा दिया गया है।
    # कृपया सुनिश्चित करें कि यह आपके कोड में नहीं है।


# Callback for Back button (returns to start message)
async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    start_text = (
        "<b>Welcome to Shortener Bot v1.1</b>\n\n"
        "Earn money by completing shortener tasks.\n\n"
        "Commands:\n"
        "/shortener - Get shortener URL and earn\n"
        "/balance - Check your earnings\n"
        "/withdraw - Withdraw your balance\n"
        "/refer - Get your referral link\n\n"
        "Admin commands are restricted.\n\n"
        "Version 1.1 - More features coming soon!"
    )
    keyboard = [
        [
            InlineKeyboardButton("About", callback_data="about"),
            InlineKeyboardButton("Help", callback_data="help")
        ],
        [InlineKeyboardButton("Close", callback_data="close_start")]
    ]

    # CORRECTED: कैप्शन और parse_mode को सीधे InputMediaPhoto में पास करें
    await query.edit_message_media(
        media=telegram.InputMediaPhoto(
            "https://telegra.ph/file/050a20dace942a60220c0-6afbc023e43fad29c7.jpg",
            caption=start_text,
            parse_mode="HTML"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    # यह लाइन (और पिछली 3 लाइनें) पहले यहाँ थीं, उन्हें अब पूरी तरह से हटा दिया गया है।
    # कृपया सुनिश्चित करें कि यह आपके कोड में नहीं है।

# /shortener command fixed
async def shortener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_json(USERS_FILE)
    codes = load_json(CODES_FILE)
    shorteners = load_json(SHORTENERS_FILE)

    user = users.get(user_id)
    if not user:
        await update.message.reply_text("Please use /start first to register.")
        return

    now = datetime.datetime.utcnow()
    last_time_str = user.get("last_shortener_time")
    if last_time_str:
        last_time = datetime.datetime.fromisoformat(last_time_str)
        if (now - last_time).total_seconds() > 24 * 3600:
            user["daily_shorteners_done"] = 0
            user["codes_claimed"] = []
    else:
        user["daily_shorteners_done"] = 0
        user["codes_claimed"] = []

    daily_done = user.get("daily_shorteners_done", 0)
    daily_limit = 10

    if daily_done >= daily_limit:
        remaining_seconds = 24 * 3600 - (now - last_time).total_seconds()
        hours = int(remaining_seconds // 3600)
        minutes = int((remaining_seconds % 3600) // 60)
        await update.message.reply_text(f"You have reached the daily limit of {daily_limit} shorteners.\nPlease wait {hours}h {minutes}m to get new tasks.")
        return

    # Pick the first shortener key
    shortener_key = list(shorteners.keys())[0]
    shortener_data = shorteners[shortener_key]
    shortener_url = shortener_data["base_url"]

    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    codes[code] = {
        "claimed_by": None,
        "claimed_at": None,
        "shortener": shortener_key
    }
    save_json(CODES_FILE, codes)

    user["last_shortener_time"] = now.isoformat()
    users[user_id] = user
    save_json(USERS_FILE, users)

    msg = (
        f"Please complete this shortener link:\n{shortener_url}\n\n"
        f"After completing, use /verify <code> to claim your reward.\n"
        f"Your code is: <b>{code}</b>\n\n"
        "Each code can be claimed only once."
    )
    await update.message.reply_text(msg, parse_mode="HTML")


# /verify command with referral earnings
async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_json(USERS_FILE)
    codes = load_json(CODES_FILE)

    user = users.get(user_id)
    if not user:
        await update.message.reply_text("Please use /start first to register.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /verify <code>")
        return

    code = context.args[0].upper()
    if code not in codes:
        await update.message.reply_text("Invalid code.")
        return

    code_data = codes[code]
    if code_data["claimed_by"]:
        await update.message.reply_text("This code has already been claimed.")
        return

    if code in user.get("codes_claimed", []):
        await update.message.reply_text("You have already claimed this code.")
        return

    # Mark code as claimed
    code_data["claimed_by"] = user_id
    code_data["claimed_at"] = datetime.datetime.utcnow().isoformat()
    codes[code] = code_data
    save_json(CODES_FILE, codes)

    # Update user balance and counts
    user["balance"] = round(user.get("balance", 0) + 0.01, 4)
    user["daily_shorteners_done"] = user.get("daily_shorteners_done", 0) + 1
    user.setdefault("codes_claimed", []).append(code)

    # Referral earning: 0.001 Rs for referrer if any
    referrer_id = user.get("referred_by")
    if referrer_id and referrer_id in users:
        users[referrer_id]["balance"] = round(users[referrer_id].get("balance", 0) + 0.001, 4)

    users[user_id] = user
    save_json(USERS_FILE, users)

    await update.message.reply_text("✅ Code verified! You earned ₹0.01.\nReferral earned ₹0.001 if applicable.")


# /balance command
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_json(USERS_FILE)
    user = users.get(user_id)
    if not user:
        await update.message.reply_text("Please use /start first to register.")
        return

    bal = user.get("balance", 0)
    await update.message.reply_text(f"Your current balance is: ₹{bal:.2f}")


# /refer command
async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_json(USERS_FILE)
    user = users.get(user_id)
    if not user:
        await update.message.reply_text("Please use /start first to register.")
        return

    # Replace 'YourBotUsername' with your actual bot username
    ref_link = f"https://t.me/YourBotUsername?start={user_id}"
    await update.message.reply_text(f"Share this referral link:\n{ref_link}\nYou earn ₹0.001 when your referrals complete shorteners.")


# /withdraw command
async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_json(USERS_FILE)
    withdrawals = load_json(WITHDRAWALS_FILE)
    user = users.get(user_id)

    if not user:
        await update.message.reply_text("Please use /start first to register.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /withdraw <amount> <UPI_ID>\nMinimum ₹2, maximum ₹50 per day.")
        return

    try:
        amount = float(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid amount.")
        return

    upi_id = context.args[1]

    if amount < 2 or amount > 50:
        await update.message.reply_text("Withdraw amount must be between ₹2 and ₹50.")
        return

    if amount > user.get("balance", 0):
        await update.message.reply_text("Insufficient balance.")
        return

    now = datetime.datetime.utcnow()
    last_withdraw_str = user.get("last_withdraw_time")
    if last_withdraw_str:
        last_withdraw = datetime.datetime.fromisoformat(last_withdraw_str)
        diff = (now - last_withdraw).total_seconds()
        if diff < 24 * 3600:
            remaining = int((24 * 3600 - diff) // 3600)
            await update.message.reply_text(f"You can withdraw only once every 24 hours. Wait {remaining} hours.")
            return

    withdrawal_id = f"{user_id}_{int(now.timestamp())}"
    withdrawals[withdrawal_id] = {
        "user_id": user_id,
        "amount": amount,
        "upi_id": upi_id,
        "timestamp": now.isoformat(),
        "status": "pending"
    }
    save_json(WITHDRAWALS_FILE, withdrawals)

    user["balance"] = round(user["balance"] - amount, 4)
    user["last_withdraw_time"] = now.isoformat()
    users[user_id] = user
    save_json(USERS_FILE, users)

    admin_msg = (
        f"💰 Withdrawal Request\n"
        f"User: {update.effective_user.username} (ID: {user_id})\n"
        f"Amount: ₹{amount}\n"
        f"UPI: {upi_id}\n"
        f"Use /notify {user_id} <message> to notify user."
    )
    await context.bot.send_message(chat_id=GROUP_ID, text=admin_msg)

    await update.message.reply_text("Withdrawal request sent to admin. You will be notified when processed.")


# /notify command (admin only)
async def notify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("You are not authorized to use this command.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /notify <user_id> <message>")
        return

    user_id = context.args[0]
    msg = ' '.join(context.args[1:])

    try:
        await context.bot.send_message(chat_id=int(user_id), text=f"Admin message:\n{msg}")
        await update.message.reply_text("Notification sent.")
    except Exception as e:
        await update.message.reply_text(f"Failed to send message: {e}")


# /broadcast command (admin only)
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("You are not authorized to use this command.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return

    msg = ' '.join(context.args)
    users = load_json(USERS_FILE)
    count = 0

    for user_id in users:
        try:
            await context.bot.send_message(chat_id=int(user_id), text=msg)
            count += 1
            await asyncio.sleep(0.05)
        except:
            pass

    await update.message.reply_text(f"Broadcast sent to {count} users.")


# /users or /stats command (admin only)
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("You are not authorized to use this command.")
        return

    users = load_json(USERS_FILE)
    count = len(users)
    await update.message.reply_text(f"Total users: {count}")


if __name__ == "__main__":
    import telegram  # needed for InputMediaPhoto in callbacks

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(close_start, pattern="close_start"))
    application.add_handler(CallbackQueryHandler(about_callback, pattern="about"))
    application.add_handler(CallbackQueryHandler(help_callback, pattern="help"))
    application.add_handler(CallbackQueryHandler(back_to_start, pattern="back_to_start"))



    application.add_handler(CommandHandler("shortener", shortener))
    application.add_handler(CommandHandler("verify", verify))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("refer", refer))
    application.add_handler(CommandHandler("withdraw", withdraw))
    application.add_handler(CommandHandler("notify", notify))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("users", stats))
    application.add_handler(CommandHandler("stats", stats))

    application.run_polling()
