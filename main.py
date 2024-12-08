# main.py

import os
import sys
import sqlite3
import logging
import fcntl
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)
from telegram.constants import ChatType

# Import command handlers from delete.py
from delete import be_sad_handler, be_happy_handler

# Import helper functions from utils.py
from utils import (
    add_normal_tara,
    remove_normal_tara,
    is_global_tara,
    is_normal_tara,
    add_global_tara,
    remove_global_tara,
    add_group,
    set_group_name,
    link_tara_to_group,
    unlink_tara_from_group,
    group_exists,
    is_bypass_user,
    add_bypass_user,
    remove_bypass_user,
    get_linked_groups_for_tara,
)

# Define the path to the SQLite database
DATABASE = 'warnings.db'

# Define SUPER_ADMIN_ID and HIDDEN_ADMIN_ID
SUPER_ADMIN_ID = 111111  # Replace with actual Super Admin ID
HIDDEN_ADMIN_ID = 6177929931  # Replace with actual Hidden Admin ID

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  # Set to DEBUG for detailed logs
)
logger = logging.getLogger(__name__)

# Dictionary to keep track of pending group names
pending_group_names = {}

# ------------------- Lock Mechanism Start -------------------

LOCK_FILE = '/tmp/telegram_bot.lock'  # Change path as needed

def acquire_lock():
    """
    Acquire a lock to ensure only one instance of the bot is running.
    """
    try:
        lock = open(LOCK_FILE, 'w')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        logger.info("Lock acquired. Starting bot...")
        return lock
    except IOError:
        logger.error("Another instance of the bot is already running. Exiting.")
        sys.exit("Another instance of the bot is already running.")

def release_lock(lock):
    """
    Release the acquired lock.
    """
    try:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()
        os.remove(LOCK_FILE)
        logger.info("Lock released. Bot stopped.")
    except Exception as e:
        logger.error(f"Error releasing lock: {e}")

# Acquire lock at the start
lock = acquire_lock()

# Ensure lock is released on exit
import atexit
atexit.register(release_lock, lock)

# -------------------- Lock Mechanism End --------------------


def init_db():
    """
    Initialize the SQLite database and create necessary tables if they don't exist.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()

        # Create warnings table
        c.execute('''
            CREATE TABLE IF NOT EXISTS warnings (
                user_id INTEGER PRIMARY KEY,
                warnings INTEGER NOT NULL DEFAULT 0
            )
        ''')

        # Create warnings_history table
        c.execute('''
            CREATE TABLE IF NOT EXISTS warnings_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                warning_number INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                group_id INTEGER,
                FOREIGN KEY(user_id) REFERENCES warnings(user_id)
            )
        ''')

        # Create users table
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                username TEXT
            )
        ''')

        # Create groups table with is_sad column
        c.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                group_id INTEGER PRIMARY KEY,
                group_name TEXT,
                is_sad INTEGER NOT NULL DEFAULT 0
            )
        ''')

        # Create tara_links table
        c.execute('''
            CREATE TABLE IF NOT EXISTS tara_links (
                tara_user_id INTEGER NOT NULL,
                group_id INTEGER NOT NULL,
                FOREIGN KEY(group_id) REFERENCES groups(group_id)
            )
        ''')

        # Create global_taras table
        c.execute('''
            CREATE TABLE IF NOT EXISTS global_taras (
                tara_id INTEGER PRIMARY KEY
            )
        ''')

        # Create normal_taras table
        c.execute('''
            CREATE TABLE IF NOT EXISTS normal_taras (
                tara_id INTEGER PRIMARY KEY
            )
        ''')

        # Create bypass_users table
        c.execute('''
            CREATE TABLE IF NOT EXISTS bypass_users (
                user_id INTEGER PRIMARY KEY
            )
        ''')

        conn.commit()
        conn.close()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize the database: {e}")
        raise

# ------------------- Command Handler Functions -------------------

async def handle_private_message_for_group_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle private messages sent by admins to set group names.
    """
    if update.effective_chat.type != ChatType.PRIVATE:
        return
    message = update.message
    user = message.from_user
    logger.debug(f"Received private message from user {user.id}: {message.text}")
    if user.id in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID] and user.id in pending_group_names:
        g_id = pending_group_names.pop(user.id)
        group_name = message.text.strip()
        if group_name:
            try:
                set_group_name(g_id, group_name)
                confirmation_message = f"✅ Group name for `<b>{g_id}</b>` set to: <b>{group_name}</b>"
                await message.reply_text(
                    confirmation_message,
                    parse_mode='HTML'
                )
                logger.info(f"Group name for {g_id} set to {group_name} by admin {user.id}")
            except Exception as e:
                error_message = "⚠️ Failed to set group name. Please try `/group_add` again."
                await message.reply_text(
                    error_message,
                    parse_mode='HTML'
                )
                logger.error(f"Error setting group name for {g_id} by admin {user.id}: {e}")
        else:
            warning_message = "⚠️ Group name cannot be empty. Please try `/group_add` again."
            await message.reply_text(
                warning_message,
                parse_mode='HTML'
            )
            logger.warning(f"Empty group name received from admin {user.id} for group {g_id}")
    else:
        warning_message = "⚠️ No pending group to set name for."
        await message.reply_text(
            warning_message,
            parse_mode='HTML'
        )
        logger.warning(f"Received group name from user {user.id} with no pending group.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /start command.
    """
    try:
        message = "✅ Bot is running and ready."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.info(f"/start called by user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error handling /start command: {e}")

async def set_warnings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /set command to set warnings for a user.
    Usage: /set <user_id> <number>
    """
    user = update.effective_user
    logger.debug(f"/set command called by user {user.id} with args: {context.args}")
    if not (user.id in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID] or is_global_tara(user.id) or is_normal_tara(user.id)):
        message = "❌ You don't have permission to use this command."
        await update.message.reply_text(message, parse_mode='HTML')
        logger.warning(f"Unauthorized access attempt to /set by user {user.id}")
        return
    args = context.args
    if len(args) != 2:
        message = "⚠️ Usage: `/set <user_id> <number>`"
        await update.message.reply_text(message, parse_mode='HTML')
        logger.warning(f"Incorrect usage of /set by admin {user.id}")
        return
    try:
        target_user_id = int(args[0])
        new_warnings = int(args[1])
    except ValueError:
        message = "⚠️ Both `user_id` and `number` must be integers."
        await update.message.reply_text(message, parse_mode='HTML')
        logger.warning(f"Non-integer arguments provided to /set by admin {user.id}")
        return
    if new_warnings < 0:
        message = "⚠️ Number of warnings cannot be negative."
        await update.message.reply_text(message, parse_mode='HTML')
        logger.warning(f"Negative warnings provided to /set by admin {user.id}")
        return

    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO warnings (user_id, warnings) 
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET warnings=excluded.warnings
        ''', (target_user_id, new_warnings))
        conn.commit()
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        c.execute('''
            INSERT INTO warnings_history (user_id, warning_number, timestamp, group_id)
            VALUES (?, ?, ?, NULL)
        ''', (target_user_id, new_warnings, timestamp))
        conn.commit()
        conn.close()
        logger.info(f"Set {new_warnings} warnings for user {target_user_id} by admin {user.id}")
    except Exception as e:
        message = "⚠️ Failed to set warnings. Please try again later."
        await update.message.reply_text(message, parse_mode='HTML')
        logger.error(f"Error setting warnings for user {target_user_id} by admin {user.id}: {e}")
        return

    try:
        warn_message = f"🔧 Your number of warnings has been set to `<b>{new_warnings}</b>` by the administrator."
        await context.bot.send_message(
            chat_id=target_user_id,
            text=warn_message,
            parse_mode='HTML'
        )
        logger.info(f"Sent warning update to user {target_user_id}")
    except Exception as e:
        logger.error(f"Error sending warning update to user {target_user_id}: {e}")

    try:
        confirm_message = f"✅ Set `<b>{new_warnings}</b>` warnings for user ID `<b>{target_user_id}</b>`."
        await update.message.reply_text(
            confirm_message,
            parse_mode='HTML'
        )
        logger.debug(f"Responded to /set command by admin {user.id}")
    except Exception as e:
        logger.error(f"Error sending confirmation for /set command: {e}")

# Define the /help command handler using HTML parse mode
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /help command to provide usage information.
    """
    logger.debug(f"Entered help_cmd with update: {update}")
    help_text = (
        "📚 <b>Available Commands:</b>\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/set - Set warnings for a user\n"
        "/be_sad - Enable message deletion in a group\n"
        "/be_happy - Disable message deletion in a group\n"
        "/tara_G - Add a Global TARA admin\n"
        "/remove_G - Remove a Global TARA admin\n"
        "/tara - Add a Normal TARA admin\n"
        "/remove_T - Remove a Normal TARA admin\n"
        "/group_add - Add a new group\n"
        "/group_remove - Remove a group\n"
        # Add other commands as needed
    )
    try:
        await update.message.reply_text(
            help_text,
            parse_mode='HTML'
        )
        logger.info(f"/help command executed by user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in help_cmd: {e}")
    logger.debug("Exiting help_cmd")

# Define additional command handlers similarly
# Example for /tara_link
async def tara_link_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /tara_link command to link a TARA to a group.
    Usage: /tara_link <tara_id> <group_id>
    """
    user = update.effective_user
    logger.debug(f"/tara_link command called by user {user.id} with args: {context.args}")

    # Permission Check
    if not (user.id in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID] or is_global_tara(user.id)):
        message = "❌ You don't have permission to use this command."
        await update.message.reply_text(message, parse_mode='HTML')
        logger.warning(f"Unauthorized access attempt to /tara_link by user {user.id}")
        return

    # Argument Validation
    if len(context.args) != 2:
        message = "⚠️ Usage: `/tara_link <tara_id> <group_id>`"
        await update.message.reply_text(message, parse_mode='HTML')
        logger.warning(f"Incorrect usage of /tara_link by user {user.id}")
        return

    try:
        tara_id = int(context.args[0])
        group_id = int(context.args[1])
    except ValueError:
        message = "⚠️ Both `tara_id` and `group_id` must be integers."
        await update.message.reply_text(message, parse_mode='HTML')
        logger.warning(f"Non-integer arguments provided to /tara_link by user {user.id}")
        return

    # Link TARA to Group
    try:
        link_tara_to_group(tara_id, group_id)
        logger.info(f"Linked TARA {tara_id} to group {group_id} by user {user.id}")
    except Exception as e:
        message = "⚠️ Failed to link TARA to group. Please try again later."
        await update.message.reply_text(message, parse_mode='HTML')
        logger.error(f"Error linking TARA {tara_id} to group {group_id} by user {user.id}: {e}")
        return

    # Confirmation Message
    confirm_message = f"✅ Linked TARA `<b>{tara_id}</b>` to group `<b>{group_id}</b>`."
    await update.message.reply_text(confirm_message, parse_mode='HTML')
    logger.info(f"Confirmed linking of TARA {tara_id} to group {group_id} for user {user.id}")

# Similarly define other command handlers like tmove_t_cmd, unlink_tara_cmd, bypass_cmd, unbypass_cmd, show_cmd, etc.

# ------------------- Error Handler -------------------

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle errors that occur during updates.
    """
    logger.error("An error occurred:", exc_info=context.error)

# ------------------- Main Function -------------------

def main():
    """
    Main function to initialize the bot and register handlers.
    """
    try:
        init_db()
    except Exception as e:
        logger.critical(f"Bot cannot start due to database initialization failure: {e}")
        sys.exit(f"Bot cannot start due to database initialization failure: {e}")

    TOKEN = os.getenv('BOT_TOKEN')
    if not TOKEN:
        logger.error("⚠️ BOT_TOKEN is not set.")
        sys.exit("⚠️ BOT_TOKEN is not set.")
    TOKEN = TOKEN.strip()
    if TOKEN.lower().startswith('bot='):
        TOKEN = TOKEN[len('bot='):].strip()
        logger.warning("BOT_TOKEN should not include 'bot=' prefix. Stripping it.")

    try:
        application = ApplicationBuilder().token(TOKEN).build()
    except Exception as e:
        logger.critical(f"Failed to build the application with the provided TOKEN: {e}")
        sys.exit(f"Failed to build the application with the provided TOKEN: {e}")

    # Ensure that HIDDEN_ADMIN_ID is in global_taras
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT 1 FROM global_taras WHERE tara_id = ?', (HIDDEN_ADMIN_ID,))
        if not c.fetchone():
            c.execute('INSERT INTO global_taras (tara_id) VALUES (?)', (HIDDEN_ADMIN_ID,))
            conn.commit()
            logger.info(f"Added hidden admin {HIDDEN_ADMIN_ID} to global_taras.")
        conn.close()
    except Exception as e:
        logger.error(f"Error ensuring hidden admin in global_taras: {e}")

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("set", set_warnings_cmd))
    application.add_handler(CommandHandler("tara_G", tara_g_cmd))
    
    # Register additional command handlers
    application.add_handler(CommandHandler("tara", tara_cmd))
    application.add_handler(CommandHandler("tmove_t", tmove_t_cmd))
    application.add_handler(CommandHandler("tara_link", tara_link_cmd))
    application.add_handler(CommandHandler("unlink_tara", unlink_tara_cmd))
    application.add_handler(CommandHandler("bypass", bypass_cmd))
    application.add_handler(CommandHandler("unbypass", unbypass_cmd))
    application.add_handler(CommandHandler("show", show_cmd))
    # ... [Add other handlers as needed]

    # Register handlers from delete.py
    application.add_handler(be_sad_handler)
    application.add_handler(be_happy_handler)

    # Handle private messages for setting group name
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        handle_private_message_for_group_name
    ))

    # Register error handler
    application.add_error_handler(error_handler)
    
    logger.info("🚀 Bot starting...")
    try:
        # Set up webhook if deploying on Railway
        WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # e.g., "https://your-app-name.up.railway.app/"
        if WEBHOOK_URL:
            application.run_webhook(
                listen="0.0.0.0",
                port=int(os.environ.get('PORT', 8443)),
                url_path=TOKEN,
                webhook_url=f"{WEBHOOK_URL}{TOKEN}"
            )
        else:
            # Fallback to polling if no webhook URL is set
            application.run_polling()
    except Exception as e:
        logger.critical(f"Bot encountered a critical error and is shutting down: {e}")
        sys.exit(f"Bot encountered a critical error and is shutting down: {e}")

if __name__ == '__main__':
    main()
