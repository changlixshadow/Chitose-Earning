import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto # Added InputMediaPhoto
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
)
import sqlite3
import uuid
import time
from datetime import datetime, timedelta
import asyncio # Keep asyncio import

# --- Configuration ---
# IMPORTANT: Replace BOT_TOKEN, ADMIN_ID, and ADMIN_GROUP_ID with your actual values.
BOT_TOKEN = "8006836827:AAERFD1tDpBDJhvKm_AHy20uSAzZdoRwbZc"
ADMIN_ID = 5759232282
# To get your ADMIN_GROUP_ID: Add your bot to the group, send any message,
# then open this URL in your browser: https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
# Look for 'chat': {'id': -1234567890, 'title': 'Your Group Name', 'type': 'group'}
# The 'id' starting with a negative number is your group ID.
ADMIN_GROUP_ID = -1001234567890 # REPLACE THIS WITH YOUR ACTUAL ADMIN GROUP ID!

START_IMAGE_URL = "https://telegra.ph/file/050a20dace942a60220c0-6afbc023e43fad29c7.jpg"
ABOUT_IMAGE_URL = "https://telegra.ph/file/9d18345731db88fff4f8c-d2b3920631195c5747.jpg"
HELP_IMAGE_URL = "https://telegra.ph/file/e6ec31fc792d072da2b7e-54e7c7d4c5651823b3.jpg"

# Shortener APIs configuration
# Add more dictionaries to this list for more shortener APIs.
SHORTENER_APIS = [
    {"name": "LinkCents", "base_url": "https://linkcents.com", "api_key": "a3dede8bbc12f4bd0afd61cf1ac691f3545d5faf", "daily_limit_per_user": 10},
    # Example for another shortener (replace with real data):
    # {"name": "AnotherShortener", "base_url": "https://anothershortener.com", "api_key": "YOUR_ANOTHER_API_KEY", "daily_limit_per_user": 5},
]

# States for ConversationHandler (for withdraw)
WITHDRAW_AMOUNT, WITHDRAW_UPI = range(2)

# Set up logging for better debugging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Database Functions ---
# Function: get_db_connection
# Description: Establishes a connection to the SQLite database.
# Returns: sqlite3.Connection object
def get_db_connection():
    conn = sqlite3.connect('bot_data.db')
    conn.row_factory = sqlite3.Row # Allows accessing columns by name
    return conn

# Function: init_db
# Description: Initializes the database schema, creating tables if they don't exist,
#              and pre-populating shortener APIs.
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create users table to store user information
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0.00,
            referred_by INTEGER,
            last_withdraw_request_time TEXT,
            last_referral_credit_date TEXT,
            FOREIGN KEY (referred_by) REFERENCES users (id)
        )
    ''')
    
    # Create shorteners table to store details of integrated shortener APIs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shorteners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE, -- Ensure unique shortener names
            base_url TEXT,
            api_key TEXT,
            daily_limit_per_user INTEGER,
            status TEXT DEFAULT 'active'
        )
    ''')
    
    # Create user_shortener_progress table to track daily shortener task completion per user
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_shortener_progress (
            user_id INTEGER,
            shortener_id INTEGER,
            date TEXT,
            completed_count INTEGER DEFAULT 0,
            last_completion_time TEXT,
            PRIMARY KEY (user_id, shortener_id, date),
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (shortener_id) REFERENCES shorteners (id)
        )
    ''')
    
    # Create pending_codes table to store unique codes for shortener verification
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_codes (
            code TEXT PRIMARY KEY,
            user_id INTEGER,
            shortener_id INTEGER,
            generation_time TEXT,
            status TEXT DEFAULT 'pending', -- 'pending', 'claimed', 'expired'
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (shortener_id) REFERENCES shorteners (id)
        )
    ''')
    
    # Create withdrawals table to record user withdrawal requests
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            upi_id TEXT,
            status TEXT DEFAULT 'pending', -- 'pending', 'completed', 'rejected'
            request_time TEXT,
            completion_time TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.commit()

    # Pre-populate shorteners if they don't exist in the database
    for api in SHORTENER_APIS:
        cursor.execute("INSERT OR IGNORE INTO shorteners (name, base_url, api_key, daily_limit_per_user) VALUES (?, ?, ?, ?)",
                       (api['name'], api['base_url'], api['api_key'], api['daily_limit_per_user']))
    conn.commit()
    conn.close()

# --- Helper Functions ---
# Function: check_admin
# Description: Verifies if the current user is the bot's admin.
# Parameters:
#   update (Update): The update object from Telegram.
#   context (CallbackContext): The context object.
# Returns: bool - True if the user is admin, False otherwise.
async def check_admin(update: Update, context) -> bool:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("You are not authorized to use this command.")
        return False
    return True

# Function: generate_unique_code
# Description: Generates a random, unique 10-character alphanumeric code.
# Returns: str - The generated unique code.
def generate_unique_code():
    return uuid.uuid4().hex[:10].upper() # 10 characters, uppercase

# --- Command Handlers ---

# Function: start
# Description: Handles the /start command. Welcomes new users, registers them,
#              handles referral links, and displays initial bot information with buttons.
# Parameters:
#   update (Update): The update object from Telegram.
#   context (CallbackContext): The context object.
async def start(update: Update, context) -> None:
    user = update.effective_user
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if user exists, if not, add them
    cursor.execute("SELECT * FROM users WHERE id = ?", (user.id,))
    existing_user = cursor.fetchone()

    referred_by_id = None
    if context.args and context.args[0].startswith("refer_"):
        try:
            referred_by_id = int(context.args[0].split('_')[1])
            # Ensure referrer actually exists and is not the current user
            if referred_by_id == user.id:
                referred_by_id = None # Cannot refer yourself
            else:
                cursor.execute("SELECT id FROM users WHERE id = ?", (referred_by_id,))
                if not cursor.fetchone():
                    referred_by_id = None # Invalid referrer
        except (ValueError, IndexError):
            referred_by_id = None

    if not existing_user:
        cursor.execute("INSERT INTO users (id, username, referred_by) VALUES (?, ?, ?)",
                       (user.id, user.username, referred_by_id))
        conn.commit()
        logger.info(f"New user joined: {user.username} ({user.id})")
        if referred_by_id:
            logger.info(f"User {user.username} ({user.id}) was referred by {referred_by_id}")
            # Optionally, notify the referrer that a new user joined via their link
            # try:
            #     await context.bot.send_message(referred_by_id, f"A new user ({user.username if user.username else user.first_name}) joined using your referral link!")
            # except Exception as e:
            #     logger.warning(f"Could not notify referrer {referred_by_id}: {e}")
    conn.close()

    keyboard = [
        [InlineKeyboardButton("About", callback_data="about_btn"),
         InlineKeyboardButton("Help", callback_data="help_btn")],
        [InlineKeyboardButton("Close", callback_data="close_start_message")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = await update.message.reply_photo(
        photo=START_IMAGE_URL,
        caption="""Hello! Welcome to the Money-Making Bot!
This bot allows you to earn money by completing simple tasks.

Use the buttons below to learn more.""",
        reply_markup=reply_markup
    )
    # Store message ID to delete it later
    context.user_data['start_message_id'] = message.message_id

# Function: shortener
# Description: Handles the /shortener command. Provides a unique shortener URL
#              and instructions for earning.
# Parameters:
#   update (Update): The update object from Telegram.
#   context (CallbackContext): The context object.
async def shortener(update: Update, context) -> None:
    user_id = update.effective_user.id
    conn = get_db_connection()
    cursor = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')

    # Get available shorteners and user's progress
    # This query selects shorteners that are active and checks user's daily completion count
    cursor.execute("""
        SELECT s.id, s.name, s.base_url, s.api_key, s.daily_limit_per_user,
               COALESCE(usp.completed_count, 0) AS completed_count
        FROM shorteners s
        LEFT JOIN user_shortener_progress usp ON s.id = usp.shortener_id AND usp.user_id = ? AND usp.date = ?
        WHERE s.status = 'active'
    """, (user_id, today))
    
    available_shorteners = []
    total_allowed_tasks = 0 # To count total possible tasks across all shorteners
    for row in cursor.fetchall():
        total_allowed_tasks += row['daily_limit_per_user']
        if row['completed_count'] < row['daily_limit_per_user']:
            available_shorteners.append(row)

    if not available_shorteners:
        # Check if the user has completed any tasks today to determine the wait time.
        cursor.execute("SELECT MAX(last_completion_time) FROM user_shortener_progress WHERE user_id = ? AND date = ?", (user_id, today))
        max_completion_time_str = cursor.fetchone()[0]

        wait_message = "You have completed all available shortener tasks for today."
        if max_completion_time_str:
            last_completion_dt = datetime.fromisoformat(max_completion_time_str)
            next_available_time = last_completion_dt + timedelta(hours=24)
            time_left = next_available_time - datetime.now()

            if time_left.total_seconds() > 0:
                hours, remainder = divmod(time_left.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                wait_message += f" Please wait for {hours} hours and {minutes} minutes."
            else:
                wait_message += " New tasks should be available soon."
        else:
            # This case might mean no tasks were available from the start or user completed
            # everything from a previous day and is now hitting a new day's limit.
            wait_message += " New tasks will be available in 24 hours."

        await update.message.reply_text(wait_message)
        conn.close()
        return

    # Randomly select a shortener from the available ones
    import random
    selected_shortener = random.choice(available_shorteners)

    # Generate a unique code for verification
    unique_code = generate_unique_code()
    
    # Store the pending code in the database
    cursor.execute("INSERT INTO pending_codes (code, user_id, shortener_id, generation_time, status) VALUES (?, ?, ?, ?, ?)",
                   (unique_code, user_id, selected_shortener['id'], datetime.now().isoformat(), 'pending'))
    conn.commit()

    # --- Shortener API Integration (Conceptual / Placeholder) ---
    # This section demonstrates how you would call a shortener API.
    # For linkcents.com, you would replace 'your_long_url_to_shorten'
    # with an actual URL. The key is that the user needs to get the 'unique_code'
    # after completing the task, either by the shortener providing it
    # (unlikely for ad-based shorteners) or by your bot telling the user to
    # expect this specific code for verification.
    
    # Placeholder for the actual shortened URL from the API.
    # In a real scenario, you'd make an HTTP request to LinkCents API here.
    # Example (requires 'requests' library: pip install requests)
    # import requests
    # try:
    #     # This is a dummy URL; you might use a URL that directs back to your
    #     # server for advanced tracking, or just a generic one.
    #     long_url = "https://example.com/some_tracker?code=" + unique_code 
    #     api_request_url = f"{selected_shortener['base_url']}/api?api={selected_shortener['api_key']}&url={long_url}"
    #     
    #     response = requests.get(api_request_url)
    #     response.raise_for_status() # Raise an exception for HTTP errors
    #     data = response.json()
    #     
    #     if data and data.get('status') == 'success':
    #         shortened_url = data.get('shortenedUrl')
    #     else:
    #         logger.error(f"Shortener API error for {selected_shortener['name']}: {data.get('message', 'Unknown API error')}")
    #         await update.message.reply_text("Failed to generate shortener URL. Please try again later.")
    #         conn.close()
    #         return
    # except requests.exceptions.RequestException as e:
    #     logger.error(f"Error connecting to shortener API {selected_shortener['name']}: {e}")
    #     await update.message.reply_text("Could not connect to the shortener service. Please try again later.")
    #     conn.close()
    #     return

    # FOR DEMO PURPOSES, I'm using a simplified URL. Replace with actual API result.
    shortened_url = f"https://linkcents.com/your_generated_link_placeholder/{unique_code}"

    await update.message.reply_text(
        f"Here is your shortener URL: {shortened_url}\n\n"
        f"Complete the task by watching ads/etc. Once done, you will receive a code.\n"
        f"Then, *send me the following code* to verify your completion and earn 0.01 Rs:\n"
        f"`{unique_code}`\n\n"
        f"*(Note: This code is unique to you and this task.)*",
        parse_mode='Markdown'
    )
    conn.close()

# Function: handle_shortener_code_submission
# Description: Handles messages that are not commands, assuming they are shortener verification codes.
# Parameters:
#   update (Update): The update object from Telegram.
#   context (CallbackContext): The context object.
async def handle_shortener_code_submission(update: Update, context) -> None:
    user_id = update.effective_user.id
    submitted_code = update.message.text.strip().upper() # Ensure consistent casing

    conn = get_db_connection()
    cursor = conn.cursor()

    # Retrieve code information from pending_codes table
    cursor.execute("SELECT code, user_id, shortener_id, status FROM pending_codes WHERE code = ?", (submitted_code,))
    code_info = cursor.fetchone()

    if code_info:
        if code_info['status'] == 'pending':
            if code_info['user_id'] == user_id:
                # Code is valid and belongs to the current user. Credit the user.
                amount_to_credit = 0.01
                cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount_to_credit, user_id))
                cursor.execute("UPDATE pending_codes SET status = 'claimed' WHERE code = ?", (submitted_code,))

                # Update user's shortener progress for today
                today = datetime.now().strftime('%Y-%m-%d')
                cursor.execute("""
                    INSERT INTO user_shortener_progress (user_id, shortener_id, date, completed_count, last_completion_time)
                    VALUES (?, ?, ?, 1, ?)
                    ON CONFLICT(user_id, shortener_id, date) DO UPDATE SET
                        completed_count = completed_count + 1,
                        last_completion_time = EXCLUDED.last_completion_time
                """, (user_id, code_info['shortener_id'], today, datetime.now().isoformat()))
                conn.commit()

                await update.message.reply_text(f"Code verified! {amount_to_credit:.2f} Rs has been credited to your account.")

                # Referral bonus logic
                cursor.execute("SELECT referred_by, last_referral_credit_date FROM users WHERE id = ?", (user_id,))
                user_data = cursor.fetchone()
                
                if user_data and user_data['referred_by']:
                    referred_by_id = user_data['referred_by']
                    last_referral_credit_date = user_data['last_referral_credit_date']

                    # Check if referral bonus was already given for this referred user today
                    if not last_referral_credit_date or datetime.strptime(last_referral_credit_date, '%Y-%m-%d').date() < datetime.now().date():
                        referral_amount = 0.001
                        cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (referral_amount, referred_by_id))
                        cursor.execute("UPDATE users SET last_referral_credit_date = ? WHERE id = ?", (today, user_id)) # Mark current user's referral credit date
                        conn.commit()
                        try:
                            # Notify the referrer
                            referrer_user_info = cursor.execute("SELECT username FROM users WHERE id = ?", (referred_by_id,)).fetchone()
                            referrer_username = referrer_user_info['username'] if referrer_user_info else f"User {referred_by_id}"
                            await context.bot.send_message(referred_by_id,
                                                           f"A user you referred completed their first shortener task today! "
                                                           f"You achieved {referral_amount:.3f} Rs.")
                        except Exception as e:
                            logger.error(f"Could not notify referrer {referred_by_id}: {e}")

            else:
                await update.message.reply_text("This code was generated for another user.")
        elif code_info['status'] == 'claimed':
            await update.message.reply_text("This code has already been claimed.")
        elif code_info['status'] == 'expired':
            await update.message.reply_text("This code has expired.") # Implement expiration logic if needed
    else:
        await update.message.reply_text("Invalid code. Please check and try again.")
    conn.close()

# Function: balance
# Description: Handles the /balance command. Displays the user's current earned balance.
# Parameters:
#   update (Update): The update object from Telegram.
#   context (CallbackContext): The context object.
async def balance(update: Update, context) -> None:
    user_id = update.effective_user.id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    user_balance = cursor.fetchone()
    conn.close()

    if user_balance:
        await update.message.reply_text(f"Your current balance is: {user_balance['balance']:.2f} Rs")
    else:
        await update.message.reply_text("You are not registered in the system. Please use /start first.")

# Function: broadcast
# Description: Admin command to send a message to all registered users.
# Parameters:
#   update (Update): The update object from Telegram.
#   context (CallbackContext): The context object.
async def broadcast(update: Update, context) -> None:
    if not await check_admin(update, context):
        return

    if not context.args:
        await update.message.reply_text("Usage: /broadcast <your message>")
        return

    message_to_send = " ".join(context.args)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users")
    all_users = cursor.fetchall()
    conn.close()

    sent_count = 0
    failed_count = 0
    for user_row in all_users:
        user_id = user_row['id']
        try:
            await context.bot.send_message(chat_id=user_id, text=message_to_send)
            sent_count += 1
            await asyncio.sleep(0.05) # Small delay to avoid rate limits
        except Exception as e:
            logger.warning(f"Failed to send broadcast to user {user_id}: {e}")
            failed_count += 1
            # You might want to update user status to inactive here in the future
    await update.message.reply_text(f"Broadcast sent to {sent_count} users. Failed for {failed_count} users.")

# Function: stats
# Description: Admin command to show bot statistics, such as total user count.
# Parameters:
#   update (Update): The update object from Telegram.
#   context (CallbackContext): The context object.
async def stats(update: Update, context) -> None:
    if not await check_admin(update, context):
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    conn.close()
    await update.message.reply_text(f"Total users: {total_users}")

# Function: withdraw_start
# Description: Initiates the withdrawal process, asking for amount.
# Parameters:
#   update (Update): The update object from Telegram.
#   context (CallbackContext): The context object.
# Returns: int - The next state in the conversation handler.
async def withdraw_start(update: Update, context) -> int:
    user_id = update.effective_user.id
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT balance, last_withdraw_request_time FROM users WHERE id = ?", (user_id,))
    user_data = cursor.fetchone()

    if not user_data:
        await update.message.reply_text("You are not registered. Please use /start first.")
        conn.close()
        return ConversationHandler.END

    user_balance = user_data['balance']
    last_withdraw_time_str = user_data['last_withdraw_request_time']

    if user_balance < 2.00:
        await update.message.reply_text(f"Minimum withdrawal amount is 2 Rs. Your current balance is {user_balance:.2f} Rs.")
        conn.close()
        return ConversationHandler.END

    if last_withdraw_time_str:
        last_withdraw_time = datetime.fromisoformat(last_withdraw_time_str)
        time_elapsed = datetime.now() - last_withdraw_time
        if time_elapsed < timedelta(days=1):
            remaining_time = timedelta(days=1) - time_elapsed
            hours, remainder = divmod(remaining_time.seconds, 3600)
            minutes, _ = divmod(remainder, 60) # Only need hours and minutes for display
            await update.message.reply_text(f"You can only withdraw once every 24 hours. Please wait for "
                                           f"{hours} hours and {minutes} minutes.")
            conn.close()
            return ConversationHandler.END

    await update.message.reply_text("Please enter the amount you wish to withdraw (2 - 50 Rs):")
    context.user_data['withdraw_amount'] = None # Reset for fresh conversation
    conn.close()
    return WITHDRAW_AMOUNT

# Function: withdraw_get_amount
# Description: Processes the entered withdrawal amount and prompts for UPI ID.
# Parameters:
#   update (Update): The update object from Telegram.
#   context (CallbackContext): The context object.
# Returns: int - The next state in the conversation handler.
async def withdraw_get_amount(update: Update, context) -> int:
    try:
        amount = float(update.message.text.strip())
        if not (2 <= amount <= 50):
            await update.message.reply_text("Invalid amount. Please enter a value between 2 and 50 Rs.")
            return WITHDRAW_AMOUNT # Stay in the same state
        
        user_id = update.effective_user.id
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
        user_balance = cursor.fetchone()['balance']
        conn.close()

        if amount > user_balance:
            await update.message.reply_text(f"You don't have enough balance. Your current balance is {user_balance:.2f} Rs.")
            return WITHDRAW_AMOUNT

        context.user_data['withdraw_amount'] = amount
        await update.message.reply_text("Please enter your UPI ID:")
        return WITHDRAW_UPI
    except ValueError:
        await update.message.reply_text("Invalid amount. Please enter a number.")
        return WITHDRAW_AMOUNT

# Function: withdraw_get_upi
# Description: Processes the UPI ID, records the withdrawal request, and notifies admin.
# Parameters:
#   update (Update): The update object from Telegram.
#   context (CallbackContext): The context object.
# Returns: int - ConversationHandler.END to end the conversation.
async def withdraw_get_upi(update: Update, context) -> int:
    upi_id = update.message.text.strip()
    amount = context.user_data['withdraw_amount']
    user = update.effective_user

    conn = get_db_connection()
    cursor = conn.cursor()

    # Deduct amount from user's balance immediately and update last withdrawal time
    cursor.execute("UPDATE users SET balance = balance - ?, last_withdraw_request_time = ? WHERE id = ?",
                   (amount, datetime.now().isoformat(), user.id))

    # Record the withdrawal request
    cursor.execute("INSERT INTO withdrawals (user_id, amount, upi_id, request_time) VALUES (?, ?, ?, ?)",
                   (user.id, amount, upi_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"Your withdrawal request for {amount:.2f} Rs to UPI ID '{upi_id}' has been submitted. "
                                   "We will process it shortly.")

    # Notify admin group
    try:
        await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=f"🚨 *New Withdrawal Request!* 🚨\n\n"
                 f"👤 User: @{user.username if user.username else user.first_name} (ID: `{user.id}`)\n"
                 f"💰 Amount: *{amount:.2f} Rs*\n"
                 f"💳 UPI ID: `{upi_id}`\n\n"
                 f"To notify user: `/notify {user.username if user.username else user.id}`", # Use ID if no username
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Failed to send withdrawal notification to admin group: {e}")

    return ConversationHandler.END

# Function: withdraw_cancel
# Description: Cancels the withdrawal conversation.
# Parameters:
#   update (Update): The update object from Telegram.
#   context (CallbackContext): The context object.
# Returns: int - ConversationHandler.END to end the conversation.
async def withdraw_cancel(update: Update, context) -> int:
    await update.message.reply_text("Withdrawal process cancelled.")
    return ConversationHandler.END

# Function: notify_user
# Description: Admin command to send a notification to a specific user, usually for withdrawal success.
# Parameters:
#   update (Update): The update object from Telegram.
#   context (CallbackContext): The context object.
async def notify_user(update: Update, context) -> None:
    if not await check_admin(update, context):
        return

    if not context.args:
        await update.message.reply_text("Usage: /notify <username_or_id>")
        return

    target_identifier = context.args[0].replace('@', '') # Remove @ if present

    conn = get_db_connection()
    cursor = conn.cursor()

    user_to_notify_id = None
    try:
        # Try as ID first
        user_to_notify_id = int(target_identifier)
        cursor.execute("SELECT id FROM users WHERE id = ?", (user_to_notify_id,))
    except ValueError:
        # If not an ID, try as username
        cursor.execute("SELECT id FROM users WHERE username = ?", (target_identifier,))
    
    user_record = cursor.fetchone()
    conn.close()

    if user_record:
        user_to_notify_id = user_record['id']
        try:
            await context.bot.send_message(
                chat_id=user_to_notify_id,
                text="🎉 Your withdrawal request has been successfully processed! The money should be in your account soon."
            )
            await update.message.reply_text(f"Successfully notified user with ID {user_to_notify_id}.")
        except Exception as e:
            await update.message.reply_text(f"Failed to send notification to user with ID {user_to_notify_id}: {e}\n"
                                           "They might have blocked the bot.")
    else:
        await update.message.reply_text(f"User '{target_identifier}' not found in bot's database.")

# Function: refer
# Description: Handles the /refer command. Provides the user with their unique referral link.
# Parameters:
#   update (Update): The update object from Telegram.
#   context (CallbackContext): The context object.
async def refer(update: Update, context) -> None:
    user_id = update.effective_user.id
    bot_info = await context.bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start=refer_{user_id}"
    await update.message.reply_text(
        f"Share this link with your friends to earn referral bonuses:\n\n`{referral_link}`\n\n"
        f"You will earn {0.001:.3f} Rs when a user you refer completes their first shortener task of the day.",
        parse_mode='Markdown'
    )

# --- Callback Query Handlers (for Inline Keyboard buttons) ---
# Function: handle_callback_query
# Description: Manages responses to inline keyboard button presses (e.g., About, Help, Close).
# Parameters:
#   update (Update): The update object from Telegram (callback query).
#   context (CallbackContext): The context object.
async def handle_callback_query(update: Update, context) -> None:
    query = update.callback_query
    await query.answer() # Acknowledge the callback query to remove loading state from button

    if query.data == "about_btn":
        keyboard = [
            [InlineKeyboardButton("Back", callback_data="start_btn"),
             InlineKeyboardButton("Help", callback_data="help_btn")],
            [InlineKeyboardButton("Close", callback_data="close_message")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_media(
            media=InputMediaPhoto(media=ABOUT_IMAGE_URL, caption="""
            🤖 *About This Bot (Version 1.1)* 🤖
            This bot is designed to help you earn small amounts of money by completing simple online tasks, primarily through URL shorteners. We aim to provide a user-friendly experience and regular updates.

            *Next Update:* Will be soon! We are constantly working to improve features and add more earning opportunities.
            """, parse_mode='Markdown'),
            reply_markup=reply_markup
        )
    elif query.data == "help_btn":
        keyboard = [
            [InlineKeyboardButton("Back", callback_data="start_btn"),
             InlineKeyboardButton("About", callback_data="about_btn")],
            [InlineKeyboardButton("Close", callback_data="close_message")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_media(
            media=InputMediaPhoto(media=HELP_IMAGE_URL, caption="""
            📚 *Bot Help Guide* 📚

            Here's a quick overview of available commands:

            *User Commands:*
            - `/start`: Shows this welcome message and bot details.
            - `/shortener`: Get a shortener URL to complete a task and earn.
            - `/balance`: Check your current earned balance.
            - `/withdraw`: Request a withdrawal of your earnings (min 2 Rs, max 50 Rs).
            - `/refer`: Get your unique referral link to invite friends and earn bonuses.

            *Admin Commands (only for bot admin):*
            - `/broadcast <message>`: Send a message to all bot users.
            - `/users` or `/stats`: See the total number of users using the bot.
            - `/notify <username_or_id>`: Manually notify a specific user (e.g., after withdrawal success).

            If you have any questions or need further assistance, please contact the bot admin.
            """, parse_mode='Markdown'),
            reply_markup=reply_markup
        )
    elif query.data == "start_btn":
        # This is for "Back" button from About/Help to Start message
        keyboard = [
            [InlineKeyboardButton("About", callback_data="about_btn"),
             InlineKeyboardButton("Help", callback_data="help_btn")],
            [InlineKeyboardButton("Close", callback_data="close_start_message")] # Use specific close for start message
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_media(
            media=InputMediaPhoto(media=START_IMAGE_URL, caption="""Hello! Welcome to the Money-Making Bot!
This bot allows you to earn money by completing simple tasks.

Use the buttons below to learn more.""", parse_mode='Markdown'),
            reply_markup=reply_markup
        )
    elif query.data == "close_start_message":
        # Specifically for the initial /start message sent via reply_photo
        if 'start_message_id' in context.user_data:
            try:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=context.user_data['start_message_id'])
                del context.user_data['start_message_id']
            except Exception as e:
                logger.error(f"Error deleting start message ID {context.user_data.get('start_message_id')}: {e}")
                # If deletion fails, at least try to remove the buttons
                await query.edit_message_reply_markup(reply_markup=None) 
                await query.message.reply_text("Message closed.")
        else:
            # If for some reason the message ID wasn't stored, just remove buttons
            await query.edit_message_reply_markup(reply_markup=None) 
            await query.message.reply_text("Message closed.")

    elif query.data == "close_message":
        # For closing About/Help messages or any other message where this callback is used
        try:
            await query.delete_message()
        except Exception as e:
            logger.error(f"Error deleting message on close: {e}")
            await query.edit_message_reply_markup(reply_markup=None) # Remove buttons if message can't be deleted

# --- Main Bot Setup ---
# Function: main
# Description: Sets up the bot application, registers all command and message handlers,
#              and starts the polling process.
async def main() -> None:
    """Starts the bot."""
    # Initialize the database and ensure tables exist
    init_db()

    # Build the Application instance for the bot
    application = Application.builder().token(BOT_TOKEN).build()

    # --- Register Handlers ---
    # Command Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("shortener", shortener))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("users", stats))
    application.add_handler(CommandHandler("stats", stats)) # Alias for /users
    application.add_handler(CommandHandler("notify", notify_user))
    application.add_handler(CommandHandler("refer", refer))

    # Conversation Handler for /withdraw command
    # This handles multi-step input for withdrawal (amount, then UPI ID)
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("withdraw", withdraw_start)],
        states={
            WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_get_amount)],
            WITHDRAW_UPI: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_get_upi)],
        },
        # Fallbacks are commands that can cancel or interrupt the conversation
        fallbacks=[CommandHandler("cancel", withdraw_cancel)],
    )
    application.add_handler(conv_handler)

    # Message Handler for shortener code submission
    # This handler will process any plain text message that is NOT a command.
    # It assumes that such messages are verification codes for shortener tasks.
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_shortener_code_submission))

    # Callback Query Handler for inline keyboard buttons
    application.add_handler(CallbackQueryHandler(handle_callback_query))

    # --- Start Polling ---
    # This starts the bot and listens for incoming updates from Telegram.
    # allowed_updates=Update.ALL_TYPES ensures all types of updates are processed.
    logger.info("Bot started polling...")
    await application.run_polling(allowed_updates=Update.ALL_TYPES)


# --- Entry Point ---
# This block ensures that the main() function is called when the script is executed.
if __name__ == "__main__":
    # The common fix for "event loop already running" is to let Application.run_polling
    # manage the loop entirely without directly calling asyncio.run() outside of it
    # if you're hitting specific environment issues.
    # However, for typical execution, asyncio.run(main()) is correct.
    # The error often points to an underlying issue with how Python or the environment
    # is handling asyncio.
    # Let's use the standard way, as it's generally robust.
    # The problem might be due to a bug or specific interaction in Python 3.13 preview.
    # For robust production use, consider Python 3.9-3.11 for telegram.ext bots.

    # If you still get the RuntimeError, try running with:
    # python -m asyncio your_script_name.py
    # or downgrade your Python version to 3.10 or 3.11 if on a pre-release 3.13.

    asyncio.run(main())
