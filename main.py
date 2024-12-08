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
    remove_group,
    set_group_name,
    link_tara_to_group,
    unlink_tara_from_group,
    group_exists,
    is_bypass_user,
    add_bypass_user,
    remove_bypass_user,
    get_linked_groups_for_tara,
    get_all_groups_and_links,
    get_warnings_info,
    test_arabic_detection,
    get_comprehensive_overview,
)

# Define the path to the SQLite database
DATABASE = 'warnings.db'

# Define SUPER_ADMIN_ID and HIDDEN_ADMIN_ID
SUPER_ADMIN_ID = 1111111111  # Replace with your actual Super Admin Telegram ID
HIDDEN_ADMIN_ID = 6177929931  # Replace with your actual Hidden Admin Telegram ID

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO  # Change to DEBUG for more detailed logs
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
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Unauthorized access attempt to /set by user {user.id}")
        return
    args = context.args
    if len(args) != 2:
        message = "⚠️ Usage: `/set <user_id> <number>`"
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Incorrect usage of /set by admin {user.id}")
        return
    try:
        target_user_id = int(args[0])
        new_warnings = int(args[1])
    except ValueError:
        message = "⚠️ Both `user_id` and `number` must be integers."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Non-integer arguments provided to /set by admin {user.id}")
        return
    if new_warnings < 0:
        message = "⚠️ Number of warnings cannot be negative."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
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
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
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

async def tara_g_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /tara_G command to add a Global TARA admin.
    Usage: /tara_G <admin_id>
    """
    user = update.effective_user
    logger.debug(f"/tara_G command called by user {user.id} with args: {context.args}")
    
    if not (user.id in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID] or is_global_tara(user.id) or is_normal_tara(user.id)):
        message = "❌ You don't have permission to use this command."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Unauthorized access attempt to /tara_G by user {user.id}")
        return
    
    if len(context.args) != 1:
        message = "⚠️ Usage: `/tara_G <admin_id>`"
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Incorrect usage of /tara_G by admin {user.id}")
        return
    
    try:
        new_admin_id = int(context.args[0])
        logger.debug(f"Parsed new_admin_id: {new_admin_id}")
    except ValueError:
        message = "⚠️ `admin_id` must be an integer."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Non-integer admin_id provided to /tara_G by admin {user.id}")
        return
    
    try:
        add_global_tara(new_admin_id)
        logger.info(f"Added Global TARA admin {new_admin_id} by user {user.id}")
    except Exception as e:
        message = "⚠️ Failed to add Global TARA. Please try again later."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.error(f"Failed to add Global TARA admin {new_admin_id} by user {user.id}: {e}")
        return

    # Ensure that hidden admin is present in global_taras
    if new_admin_id == HIDDEN_ADMIN_ID:
        logger.info("Hidden admin added to global_taras.")

    try:
        confirm_message = f"✅ Added Global TARA admin `<b>{new_admin_id}</b>`."
        await update.message.reply_text(
            confirm_message,
            parse_mode='HTML'
        )
        logger.info(f"Added Global TARA admin {new_admin_id} by user {user.id}")
    except Exception as e:
        logger.error(f"Error sending reply for /tara_G command: {e}")

async def rmove_g_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /rmove_G command to remove a Global TARA admin.
    Usage: /rmove_G <tara_id>
    """
    user = update.effective_user
    logger.debug(f"/rmove_G command called by user {user.id} with args: {context.args}")
    
    if not (user.id in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID] or is_global_tara(user.id)):
        message = "❌ You don't have permission to use this command."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Unauthorized access attempt to /rmove_G by user {user.id}")
        return
    
    if len(context.args) != 1:
        message = "⚠️ Usage: `/rmove_G <tara_id>`"
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Incorrect usage of /rmove_G by admin {user.id}")
        return
    
    try:
        tara_id = int(context.args[0])
        logger.debug(f"Parsed tara_id: {tara_id}")
    except ValueError:
        message = "⚠️ `tara_id` must be an integer."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Non-integer tara_id provided to /rmove_G by admin {user.id}")
        return
    
    try:
        remove_global_tara(tara_id)
        logger.info(f"Removed Global TARA admin {tara_id} by user {user.id}")
    except Exception as e:
        message = "⚠️ Failed to remove Global TARA. Please try again later."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.error(f"Failed to remove Global TARA admin {tara_id} by user {user.id}: {e}")
        return
    
    try:
        confirm_message = f"✅ Removed Global TARA admin `<b>{tara_id}</b>`."
        await update.message.reply_text(
            confirm_message,
            parse_mode='HTML'
        )
        logger.info(f"Confirmed removal of Global TARA admin {tara_id} by user {user.id}")
    except Exception as e:
        logger.error(f"Error sending confirmation for /rmove_G command: {e}")

async def tara_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /tara command to add a Normal TARA admin.
    Usage: /tara <tara_id>
    """
    user = update.effective_user
    logger.debug(f"/tara command called by user {user.id} with args: {context.args}")

    if not (user.id in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID] or is_global_tara(user.id)):
        message = "❌ You don't have permission to use this command."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Unauthorized access attempt to /tara by user {user.id}")
        return

    if len(context.args) != 1:
        message = "⚠️ Usage: `/tara <tara_id>`"
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Incorrect usage of /tara by admin {user.id}")
        return

    try:
        tara_id = int(context.args[0])
        logger.debug(f"Parsed tara_id: {tara_id}")
    except ValueError:
        message = "⚠️ `tara_id` must be an integer."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Non-integer tara_id provided to /tara by admin {user.id}")
        return

    try:
        add_normal_tara(tara_id)
        logger.info(f"Added Normal TARA admin {tara_id} by user {user.id}")
    except Exception as e:
        message = "⚠️ Failed to add Normal TARA. Please try again later."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.error(f"Failed to add Normal TARA admin {tara_id} by user {user.id}: {e}")
        return

    try:
        confirm_message = f"✅ Added Normal TARA admin `<b>{tara_id}</b>`."
        await update.message.reply_text(
            confirm_message,
            parse_mode='HTML'
        )
        logger.info(f"Confirmed addition of Normal TARA admin {tara_id} by user {user.id}")
    except Exception as e:
        logger.error(f"Error sending confirmation for /tara command: {e}")

async def rmove_t_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /rmove_t command to remove a Normal TARA admin.
    Usage: /rmove_t <tara_id>
    """
    user = update.effective_user
    logger.debug(f"/rmove_t command called by user {user.id} with args: {context.args}")
    
    if not (user.id in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID] or is_global_tara(user.id)):
        message = "❌ You don't have permission to use this command."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Unauthorized access attempt to /rmove_t by user {user.id}")
        return
    
    if len(context.args) != 1:
        message = "⚠️ Usage: `/rmove_t <tara_id>`"
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Incorrect usage of /rmove_t by admin {user.id}")
        return
    
    try:
        tara_id = int(context.args[0])
        logger.debug(f"Parsed tara_id: {tara_id}")
    except ValueError:
        message = "⚠️ `tara_id` must be an integer."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Non-integer tara_id provided to /rmove_t by admin {user.id}")
        return
    
    try:
        remove_normal_tara(tara_id)
        logger.info(f"Removed Normal TARA admin {tara_id} by user {user.id}")
    except Exception as e:
        message = "⚠️ Failed to remove Normal TARA. Please try again later."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.error(f"Failed to remove Normal TARA admin {tara_id} by user {user.id}: {e}")
        return
    
    try:
        confirm_message = f"✅ Removed Normal TARA admin `<b>{tara_id}</b>`."
        await update.message.reply_text(
            confirm_message,
            parse_mode='HTML'
        )
        logger.info(f"Confirmed removal of Normal TARA admin {tara_id} by user {user.id}")
    except Exception as e:
        logger.error(f"Error sending confirmation for /rmove_t command: {e}")

async def group_add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /group_add command to register a new group.
    Usage: /group_add <group_id>
    """
    user = update.effective_user
    logger.debug(f"/group_add command called by user {user.id} with args: {context.args}")
    
    if not (user.id in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID] or is_global_tara(user.id)):
        message = "❌ You don't have permission to use this command."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Unauthorized access attempt to /group_add by user {user.id}")
        return
    
    if len(context.args) != 1:
        message = "⚠️ Usage: `/group_add <group_id>`"
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Incorrect usage of /group_add by admin {user.id}")
        return
    
    try:
        group_id = int(context.args[0])
        logger.debug(f"Parsed group_id: {group_id}")
    except ValueError:
        message = "⚠️ `group_id` must be an integer."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Non-integer group_id provided to /group_add by admin {user.id}")
        return
    
    try:
        if group_exists(group_id):
            message = "⚠️ This group is already registered."
            await update.message.reply_text(
                message,
                parse_mode='HTML'
            )
            logger.warning(f"Attempt to add already registered group {group_id} by user {user.id}")
            return
        add_group(group_id)
        logger.info(f"Added group {group_id} by user {user.id}")
    except Exception as e:
        message = "⚠️ Failed to add group. Please try again later."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.error(f"Failed to add group {group_id} by user {user.id}: {e}")
        return
    
    try:
        confirmation_message = f"✅ Group `<b>{group_id}</b>` has been registered successfully."
        await update.message.reply_text(
            confirmation_message,
            parse_mode='HTML'
        )
        logger.info(f"Confirmed registration of group {group_id} by user {user.id}")
    except Exception as e:
        logger.error(f"Error sending confirmation for /group_add command: {e}")

async def rmove_group_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /rmove_group command to remove a registered group.
    Usage: /rmove_group <group_id>
    """
    user = update.effective_user
    logger.debug(f"/rmove_group command called by user {user.id} with args: {context.args}")
    
    if not (user.id in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID] or is_global_tara(user.id)):
        message = "❌ You don't have permission to use this command."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Unauthorized access attempt to /rmove_group by user {user.id}")
        return
    
    if len(context.args) != 1:
        message = "⚠️ Usage: `/rmove_group <group_id>`"
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Incorrect usage of /rmove_group by admin {user.id}")
        return
    
    try:
        group_id = int(context.args[0])
        logger.debug(f"Parsed group_id: {group_id}")
    except ValueError:
        message = "⚠️ `group_id` must be an integer."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Non-integer group_id provided to /rmove_group by admin {user.id}")
        return
    
    try:
        if not group_exists(group_id):
            message = "⚠️ This group is not registered."
            await update.message.reply_text(
                message,
                parse_mode='HTML'
            )
            logger.warning(f"Attempt to remove non-registered group {group_id} by user {user.id}")
            return
        remove_group(group_id)
        logger.info(f"Removed group {group_id} by user {user.id}")
    except Exception as e:
        message = "⚠️ Failed to remove group. Please try again later."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.error(f"Failed to remove group {group_id} by user {user.id}: {e}")
        return
    
    try:
        confirmation_message = f"✅ Group `<b>{group_id}</b>` has been removed successfully."
        await update.message.reply_text(
            confirmation_message,
            parse_mode='HTML'
        )
        logger.info(f"Confirmed removal of group {group_id} by user {user.id}")
    except Exception as e:
        logger.error(f"Error sending confirmation for /rmove_group command: {e}")

async def tara_link_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /tara_link command to link a TARA to a group.
    Usage: /tara_link <tara_id> <group_id>
    """
    user = update.effective_user
    logger.debug(f"/tara_link command called by user {user.id} with args: {context.args}")
    
    if not (user.id in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID] or is_global_tara(user.id) or is_normal_tara(user.id)):
        message = "❌ You don't have permission to use this command."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Unauthorized access attempt to /tara_link by user {user.id}")
        return
    
    if len(context.args) != 2:
        message = "⚠️ Usage: `/tara_link <tara_id> <group_id>`"
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Incorrect usage of /tara_link by admin {user.id}")
        return
    
    try:
        tara_id = int(context.args[0])
        group_id = int(context.args[1])
        logger.debug(f"Parsed tara_id: {tara_id}, group_id: {group_id}")
    except ValueError:
        message = "⚠️ Both `tara_id` and `group_id` must be integers."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Non-integer arguments provided to /tara_link by admin {user.id}")
        return
    
    try:
        if not group_exists(group_id):
            message = "⚠️ The specified group is not registered."
            await update.message.reply_text(
                message,
                parse_mode='HTML'
            )
            logger.warning(f"Attempt to link TARA to unregistered group {group_id} by user {user.id}")
            return
        link_tara_to_group(tara_id, group_id)
        logger.info(f"Linked TARA {tara_id} to group {group_id} by user {user.id}")
    except Exception as e:
        message = "⚠️ Failed to link TARA to group. Please ensure both IDs are correct."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.error(f"Error linking TARA {tara_id} to group {group_id} by user {user.id}: {e}")
        return
    
    try:
        confirmation_message = f"✅ Linked TARA `<b>{tara_id}</b>` to group `<b>{group_id}</b>` successfully."
        await update.message.reply_text(
            confirmation_message,
            parse_mode='HTML'
        )
        logger.info(f"Confirmed linking of TARA {tara_id} to group {group_id} by user {user.id}")
    except Exception as e:
        logger.error(f"Error sending confirmation for /tara_link command: {e}")

async def unlink_tara_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /unlink_tara command to unlink a TARA from a group.
    Usage: /unlink_tara <tara_id> <group_id>
    """
    user = update.effective_user
    logger.debug(f"/unlink_tara command called by user {user.id} with args: {context.args}")
    
    if not (user.id in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID] or is_global_tara(user.id) or is_normal_tara(user.id)):
        message = "❌ You don't have permission to use this command."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Unauthorized access attempt to /unlink_tara by user {user.id}")
        return
    
    if len(context.args) != 2:
        message = "⚠️ Usage: `/unlink_tara <tara_id> <group_id>`"
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Incorrect usage of /unlink_tara by admin {user.id}")
        return
    
    try:
        tara_id = int(context.args[0])
        group_id = int(context.args[1])
        logger.debug(f"Parsed tara_id: {tara_id}, group_id: {group_id}")
    except ValueError:
        message = "⚠️ Both `tara_id` and `group_id` must be integers."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Non-integer arguments provided to /unlink_tara by admin {user.id}")
        return
    
    try:
        unlink_tara_from_group(tara_id, group_id)
        logger.info(f"Unlinked TARA {tara_id} from group {group_id} by user {user.id}")
    except Exception as e:
        message = "⚠️ Failed to unlink TARA from group. Please ensure both IDs are correct."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.error(f"Error unlinking TARA {tara_id} from group {group_id} by user {user.id}: {e}")
        return
    
    try:
        confirmation_message = f"✅ Unlinked TARA `<b>{tara_id}</b>` from group `<b>{group_id}</b>` successfully."
        await update.message.reply_text(
            confirmation_message,
            parse_mode='HTML'
        )
        logger.info(f"Confirmed unlinking of TARA {tara_id} from group {group_id} by user {user.id}")
    except Exception as e:
        logger.error(f"Error sending confirmation for /unlink_tara command: {e}")

async def bypass_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /bypass command to add a user to bypass warnings.
    Usage: /bypass <user_id>
    """
    user = update.effective_user
    logger.debug(f"/bypass command called by user {user.id} with args: {context.args}")
    
    if not (user.id in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID] or is_global_tara(user.id)):
        message = "❌ You don't have permission to use this command."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Unauthorized access attempt to /bypass by user {user.id}")
        return
    
    if len(context.args) != 1:
        message = "⚠️ Usage: `/bypass <user_id>`"
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Incorrect usage of /bypass by admin {user.id}")
        return
    
    try:
        bypass_user_id = int(context.args[0])
        logger.debug(f"Parsed bypass_user_id: {bypass_user_id}")
    except ValueError:
        message = "⚠️ `user_id` must be an integer."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Non-integer user_id provided to /bypass by admin {user.id}")
        return
    
    try:
        add_bypass_user(bypass_user_id)
        logger.info(f"Added user {bypass_user_id} to bypass by admin {user.id}")
    except Exception as e:
        message = "⚠️ Failed to add user to bypass. Please try again later."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.error(f"Failed to add user {bypass_user_id} to bypass by admin {user.id}: {e}")
        return
    
    try:
        confirmation_message = f"✅ User `<b>{bypass_user_id}</b>` has been added to bypass warnings."
        await update.message.reply_text(
            confirmation_message,
            parse_mode='HTML'
        )
        logger.info(f"Confirmed addition of user {bypass_user_id} to bypass by admin {user.id}")
    except Exception as e:
        logger.error(f"Error sending confirmation for /bypass command: {e}")

async def unbypass_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /unbypass command to remove a user from bypass warnings.
    Usage: /unbypass <user_id>
    """
    user = update.effective_user
    logger.debug(f"/unbypass command called by user {user.id} with args: {context.args}")
    
    if not (user.id in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID] or is_global_tara(user.id)):
        message = "❌ You don't have permission to use this command."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Unauthorized access attempt to /unbypass by user {user.id}")
        return
    
    if len(context.args) != 1:
        message = "⚠️ Usage: `/unbypass <user_id>`"
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Incorrect usage of /unbypass by admin {user.id}")
        return
    
    try:
        bypass_user_id = int(context.args[0])
        logger.debug(f"Parsed bypass_user_id: {bypass_user_id}")
    except ValueError:
        message = "⚠️ `user_id` must be an integer."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Non-integer user_id provided to /unbypass by admin {user.id}")
        return
    
    try:
        remove_bypass_user(bypass_user_id)
        logger.info(f"Removed user {bypass_user_id} from bypass by admin {user.id}")
    except Exception as e:
        message = "⚠️ Failed to remove user from bypass. Please try again later."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.error(f"Failed to remove user {bypass_user_id} from bypass by admin {user.id}: {e}")
        return
    
    try:
        confirmation_message = f"✅ User `<b>{bypass_user_id}</b>` has been removed from bypass warnings."
        await update.message.reply_text(
            confirmation_message,
            parse_mode='HTML'
        )
        logger.info(f"Confirmed removal of user {bypass_user_id} from bypass by admin {user.id}")
    except Exception as e:
        logger.error(f"Error sending confirmation for /unbypass command: {e}")

async def show_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /show command to display all groups and linked TARAs.
    Usage: /show
    """
    user = update.effective_user
    logger.debug(f"/show command called by user {user.id} with args: {context.args}")
    
    if not (user.id in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID] or is_global_tara(user.id)):
        message = "❌ You don't have permission to use this command."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Unauthorized access attempt to /show by user {user.id}")
        return
    
    try:
        groups_and_links = get_all_groups_and_links()
        if not groups_and_links:
            message = "⚠️ No groups or linked TARAs found."
        else:
            message_lines = ["📋 <b>Registered Groups and Linked TARAs:</b>"]
            for group in groups_and_links:
                group_id = group['group_id']
                group_name = group['group_name']
                taras = group['taras']
                taras_str = ', '.join([f"<b>{tara_id}</b>" for tara_id in taras]) if taras else "None"
                message_lines.append(f"• <b>Group ID:</b> {group_id}\n  <b>Group Name:</b> {group_name}\n  <b>Linked TARAs:</b> {taras_str}")
            message = "\n".join(message_lines)
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.info(f"/show command executed by user {user.id}")
    except Exception as e:
        message = "⚠️ Failed to retrieve groups and TARAs. Please try again later."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.error(f"Error handling /show command by user {user.id}: {e}")

async def info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /info command to display warnings information.
    Usage: /info <user_id>
    """
    user = update.effective_user
    logger.debug(f"/info command called by user {user.id} with args: {context.args}")
    
    if not (user.id in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID] or is_global_tara(user.id)):
        message = "❌ You don't have permission to use this command."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Unauthorized access attempt to /info by user {user.id}")
        return
    
    if len(context.args) != 1:
        message = "⚠️ Usage: `/info <user_id>`"
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Incorrect usage of /info by user {user.id}")
        return
    
    try:
        target_user_id = int(context.args[0])
        logger.debug(f"Parsed target_user_id: {target_user_id}")
    except ValueError:
        message = "⚠️ `user_id` must be an integer."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Non-integer user_id provided to /info by user {user.id}")
        return
    
    try:
        warnings_info = get_warnings_info(target_user_id)
        if not warnings_info:
            message = "⚠️ No warnings found for this user."
        else:
            message_lines = [f"📊 <b>Warnings Information for User {target_user_id}:</b>"]
            for info in warnings_info:
                number = info['warning_number']
                timestamp = info['timestamp']
                group_id = info['group_id'] if info['group_id'] else "N/A"
                message_lines.append(f"• <b>Warning #{number}</b> at {timestamp} in Group ID: {group_id}")
            message = "\n".join(message_lines)
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.info(f"/info command executed by user {user.id} for user {target_user_id}")
    except Exception as e:
        message = "⚠️ Failed to retrieve warnings information. Please try again later."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.error(f"Error handling /info command by user {user.id}: {e}")

async def test_arabic_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /test_arabic command to test Arabic detection.
    Usage: /test_arabic <text>
    """
    user = update.effective_user
    logger.debug(f"/test_arabic command called by user {user.id} with args: {context.args}")
    
    if not (user.id in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID] or is_bypass_user(user.id)):
        message = "❌ You don't have permission to use this command."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Unauthorized access attempt to /test_arabic by user {user.id}")
        return
    
    if len(context.args) < 1:
        message = "⚠️ Usage: `/test_arabic <text>`"
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Incorrect usage of /test_arabic by user {user.id}")
        return
    
    text = ' '.join(context.args)
    try:
        result = test_arabic_detection(text)
        message = f"🔍 Arabic Detection Result: {result}"
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.info(f"/test_arabic command executed by user {user.id} with result: {result}")
    except Exception as e:
        message = "⚠️ Failed to process the text. Please try again later."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.error(f"Error handling /test_arabic command by user {user.id}: {e}")

async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /list command to provide a comprehensive overview.
    Usage: /list
    """
    user = update.effective_user
    logger.debug(f"/list command called by user {user.id} with args: {context.args}")
    
    if not (user.id in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID] or is_global_tara(user.id)):
        message = "❌ You don't have permission to use this command."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Unauthorized access attempt to /list by user {user.id}")
        return
    
    try:
        overview = get_comprehensive_overview()
        if not overview:
            message = "⚠️ No data available."
        else:
            message = "📊 <b>Comprehensive Overview:</b>\n"
            # Groups and Members
            message += "\n<b>• Groups and Members:</b>\n"
            for group in overview['groups']:
                group_id = group['group_id']
                group_name = group['group_name']
                members = ', '.join([str(member) for member in group['members']]) if group['members'] else "No Members"
                message += f"  - Group ID: {group_id}, Name: {group_name}\n    Members: {members}\n"
            # TARAs
            message += "\n<b>• TARAs:</b>\n"
            for tara in overview['taras']:
                tara_id = tara['tara_id']
                tara_type = "Global" if tara['is_global'] else "Normal"
                linked_groups = ', '.join([str(gid) for gid in tara['linked_groups']]) if tara['linked_groups'] else "No Linked Groups"
                message += f"  - TARA ID: {tara_id}, Type: {tara_type}\n    Linked Groups: {linked_groups}\n"
            # Bypassed Users
            message += "\n<b>• Bypassed Users:</b>\n"
            if overview['bypassed_users']:
                message += ', '.join([str(uid) for uid in overview['bypassed_users']])
            else:
                message += "No Bypassed Users."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.info(f"/list command executed by user {user.id}")
    except Exception as e:
        message = "⚠️ Failed to retrieve comprehensive overview. Please try again later."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.error(f"Error handling /list command by user {user.id}: {e}")

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
    application.add_handler(CommandHandler("help", help_cmd))  # /help is already working
    application.add_handler(CommandHandler("set", set_warnings_cmd))
    application.add_handler(CommandHandler("tara_G", tara_g_cmd))
    application.add_handler(CommandHandler("rmove_G", rmove_g_cmd))
    application.add_handler(CommandHandler("tara", tara_cmd))
    application.add_handler(CommandHandler("rmove_t", rmove_t_cmd))
    application.add_handler(CommandHandler("group_add", group_add_cmd))
    application.add_handler(CommandHandler("rmove_group", rmove_group_cmd))
    application.add_handler(CommandHandler("tara_link", tara_link_cmd))
    application.add_handler(CommandHandler("unlink_tara", unlink_tara_cmd))
    application.add_handler(CommandHandler("bypass", bypass_cmd))
    application.add_handler(CommandHandler("unbypass", unbypass_cmd))
    application.add_handler(CommandHandler("show", show_cmd))
    application.add_handler(CommandHandler("info", info_cmd))
    application.add_handler(CommandHandler("test_arabic", test_arabic_cmd))
    application.add_handler(CommandHandler("list", list_cmd))
    # /be_sad and /be_happy are handled in delete.py
    # Ensure they are properly imported and added

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
