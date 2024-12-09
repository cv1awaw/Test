# main.py

import os
import sys
import sqlite3
import logging
import fcntl
from datetime import datetime
import re

from telegram import Update, ChatType
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)
from telegram.helpers import escape_markdown

# Import functions from warning_handler.py
from warning_handler import (
    handle_warnings,
    is_bypass_user,
    add_bypass_user,
    remove_bypass_user,
    get_user_warnings,
    update_warnings,
    log_warning,
    group_exists,
    get_group_taras,
    check_arabic,
)

# ------------------- Configuration -------------------

# Define SUPER_ADMIN_ID and HIDDEN_ADMIN_ID for permissions
SUPER_ADMIN_ID = 1111111111  # Replace with actual Super Admin ID
HIDDEN_ADMIN_ID = 6177929931  # Replace with actual Hidden Admin ID

# Define the path to the SQLite database
DATABASE = 'warnings.db'

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO  # Change to DEBUG for more verbose output
)
logger = logging.getLogger(__name__)

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


# ------------------- Database Initialization -------------------

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

        # Create groups table
        c.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                group_id INTEGER PRIMARY KEY,
                group_name TEXT,
                delete_enabled BOOLEAN NOT NULL DEFAULT 0
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

# Initialize the database
init_db()

# ------------------- Database Helper Functions -------------------

def add_normal_tara(tara_id):
    """
    Add a normal TARA (Telegram Admin) by their user ID.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO normal_taras (tara_id) VALUES (?)', (tara_id,))
        conn.commit()
        conn.close()
        logger.info(f"Added normal TARA {tara_id}")
    except Exception as e:
        logger.error(f"Error adding normal TARA {tara_id}: {e}")
        raise

def remove_normal_tara(tara_id):
    """
    Remove a normal TARA by their user ID.
    Returns True if a record was deleted, False otherwise.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('DELETE FROM normal_taras WHERE tara_id = ?', (tara_id,))
        changes = c.rowcount
        conn.commit()
        conn.close()
        if changes > 0:
            logger.info(f"Removed normal TARA {tara_id}")
            return True
        else:
            logger.warning(f"Normal TARA {tara_id} not found")
            return False
    except Exception as e:
        logger.error(f"Error removing normal TARA {tara_id}: {e}")
        return False

def add_global_tara(tara_id):
    """
    Add a global TARA by their user ID.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO global_taras (tara_id) VALUES (?)', (tara_id,))
        conn.commit()
        conn.close()
        logger.info(f"Added global TARA {tara_id}")
    except Exception as e:
        logger.error(f"Error adding global TARA {tara_id}: {e}")
        raise

def remove_global_tara(tara_id):
    """
    Remove a global TARA by their user ID.
    Returns True if a record was deleted, False otherwise.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('DELETE FROM global_taras WHERE tara_id = ?', (tara_id,))
        changes = c.rowcount
        conn.commit()
        conn.close()
        if changes > 0:
            logger.info(f"Removed global TARA {tara_id}")
            return True
        else:
            logger.warning(f"Global TARA {tara_id} not found")
            return False
    except Exception as e:
        logger.error(f"Error removing global TARA {tara_id}: {e}")
        return False

def add_group(group_id):
    """
    Add a group by its chat ID.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO groups (group_id, group_name) VALUES (?, ?)', (group_id, None))
        conn.commit()
        conn.close()
        logger.info(f"Added group {group_id} to database with no name.")
    except Exception as e:
        logger.error(f"Error adding group {group_id}: {e}")
        raise

def set_group_name(g_id, group_name):
    """
    Set the name of a group.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('UPDATE groups SET group_name = ? WHERE group_id = ?', (group_name, g_id))
        conn.commit()
        conn.close()
        logger.info(f"Set name for group {g_id}: {group_name}")
    except Exception as e:
        logger.error(f"Error setting group name for {g_id}: {e}")
        raise

def link_tara_to_group(tara_id, g_id):
    """
    Link a TARA to a group.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        # Check if the group exists
        c.execute('SELECT 1 FROM groups WHERE group_id = ?', (g_id,))
        if not c.fetchone():
            logger.warning(f"Group {g_id} does not exist. Cannot link TARA {tara_id}.")
            conn.close()
            return False
        # Link the TARA
        c.execute('INSERT INTO tara_links (tara_user_id, group_id) VALUES (?, ?)', (tara_id, g_id))
        conn.commit()
        conn.close()
        logger.info(f"Linked TARA {tara_id} to group {g_id}")
        return True
    except Exception as e:
        logger.error(f"Error linking TARA {tara_id} to group {g_id}: {e}")
        return False

def unlink_tara_from_group(tara_id, g_id):
    """
    Unlink a TARA from a group.
    Returns True if a record was deleted, False otherwise.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('DELETE FROM tara_links WHERE tara_user_id = ? AND group_id = ?', (tara_id, g_id))
        changes = c.rowcount
        conn.commit()
        conn.close()
        if changes > 0:
            logger.info(f"Unlinked TARA {tara_id} from group {g_id}")
            return True
        else:
            logger.warning(f"No link found between TARA {tara_id} and group {g_id}")
            return False
    except Exception as e:
        logger.error(f"Error unlinking TARA {tara_id} from group {g_id}: {e}")
        return False

def is_delete_enabled(group_id):
    """
    Check if message deletion is enabled for the given group.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT delete_enabled FROM groups WHERE group_id = ?', (group_id,))
        result = c.fetchone()
        conn.close()
        if result:
            return bool(result[0])
        else:
            return False
    except Exception as e:
        logger.error(f"Error checking delete_enabled status for group {group_id}: {e}")
        return False

# ------------------- Utility Functions -------------------

def check_arabic(text):
    """
    Check if the provided text contains Arabic characters.
    Returns True if Arabic is detected, False otherwise.
    """
    arabic_regex = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]')
    return bool(arabic_regex.search(text))

# ------------------- Command Handler Functions -------------------

pending_group_names = {}

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
                escaped_group_name = escape_markdown(group_name, version=2)
                set_group_name(g_id, group_name)
                confirmation_message = escape_markdown(
                    f"✅ Group name for `{g_id}` set to: *{escaped_group_name}*",
                    version=2
                )
                await message.reply_text(
                    confirmation_message,
                    parse_mode='MarkdownV2'
                )
                logger.info(f"Group name for {g_id} set to {group_name} by admin {user.id}")
            except Exception as e:
                error_message = escape_markdown("⚠️ Failed to set group name. Please try `/group_add` again\.", version=2)
                await message.reply_text(
                    error_message,
                    parse_mode='MarkdownV2'
                )
                logger.error(f"Error setting group name for {g_id} by admin {user.id}: {e}")
        else:
            warning_message = escape_markdown("⚠️ Group name cannot be empty\. Please try `/group_add` again\.", version=2)
            await message.reply_text(
                warning_message,
                parse_mode='MarkdownV2'
            )
            logger.warning(f"Empty group name received from admin {user.id} for group {g_id}")
    else:
        warning_message = escape_markdown("⚠️ No pending group to set name for\.", version=2)
        await message.reply_text(
            warning_message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Received group name from user {user.id} with no pending group.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /start command.
    """
    try:
        message = escape_markdown("✅ Bot is running and ready\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.info(f"/start called by user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error handling /start command: {e}")

async def tara_g_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /tara_G command to add a Global TARA admin.
    Usage: /tara_G <admin_id>
    """
    user = update.effective_user
    logger.debug(f"/tara_G command called by user {user.id} with args: {context.args}")
    
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /tara_G by user {user.id}")
        return
    
    if len(context.args) != 1:
        message = escape_markdown("⚠️ Usage: `/tara_G <admin_id>`", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /tara_G by admin {user.id}")
        return
    
    try:
        new_admin_id = int(context.args[0])
        logger.debug(f"Parsed new_admin_id: {new_admin_id}")
    except ValueError:
        message = escape_markdown("⚠️ `admin_id` must be an integer\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer admin_id provided to /tara_G by admin {user.id}")
        return
    
    try:
        add_global_tara(new_admin_id)
        logger.debug(f"Added global TARA {new_admin_id} to database.")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to add global TARA\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.error(f"Failed to add global TARA admin {new_admin_id} by admin {user.id}: {e}")
        return

    # Ensure that hidden admin is present in global_taras
    if new_admin_id == HIDDEN_ADMIN_ID:
        logger.info("Hidden admin added to global_taras\.")

    try:
        confirm_message = escape_markdown(
            f"✅ Added global TARA admin `{new_admin_id}`\.",
            version=2
        )
        await update.message.reply_text(
            confirm_message,
            parse_mode='MarkdownV2'
        )
        logger.info(f"Added global TARA admin {new_admin_id} by admin {user.id}")
    except Exception as e:
        logger.error(f"Error sending reply for /tara_G command: {e}")

async def remove_global_tara_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /rmove_G command to remove a Global TARA admin.
    Usage: /rmove_G <tara_id>
    """
    user = update.effective_user
    logger.debug(f"/rmove_G command called by user {user.id} with args: {context.args}")
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /rmove_G by user {user.id}")
        return
    if len(context.args) != 1:
        message = escape_markdown("⚠️ Usage: `/rmove_G <tara_id>`", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /rmove_G by admin {user.id}")
        return
    try:
        tara_id = int(context.args[0])
        logger.debug(f"Parsed tara_id: {tara_id}")
    except ValueError:
        message = escape_markdown("⚠️ `tara_id` must be an integer\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer tara_id provided to /rmove_G by admin {user.id}")
        return

    # Prevent removal of hidden_admin
    if tara_id == HIDDEN_ADMIN_ID:
        message = escape_markdown("⚠️ Cannot remove the hidden admin\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Attempted to remove hidden admin {tara_id} by admin {user.id}")
        return

    try:
        if remove_global_tara(tara_id):
            confirm_message = escape_markdown(
                f"✅ Removed global TARA `{tara_id}`\.",
                version=2
            )
            await update.message.reply_text(
                confirm_message,
                parse_mode='MarkdownV2'
            )
            logger.info(f"Removed global TARA {tara_id} by admin {user.id}")
        else:
            warning_message = escape_markdown(
                f"⚠️ Global TARA `{tara_id}` not found\.",
                version=2
            )
            await update.message.reply_text(
                warning_message,
                parse_mode='MarkdownV2'
            )
            logger.warning(f"Attempted to remove non-existent global TARA {tara_id} by admin {user.id}")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to remove global TARA\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error removing global TARA {tara_id} by admin {user.id}: {e}")

async def tara_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /tara command to add a normal TARA.
    Usage: /tara <tara_id>
    """
    user = update.effective_user
    logger.debug(f"/tara command called by user {user.id} with args: {context.args}")
    
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /tara by user {user.id}")
        return
    
    if len(context.args) != 1:
        message = escape_markdown("⚠️ Usage: `/tara <tara_id>`", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /tara by admin {user.id}")
        return
    
    try:
        tara_id = int(context.args[0])
        logger.debug(f"Parsed tara_id: {tara_id}")
    except ValueError:
        message = escape_markdown("⚠️ `tara_id` must be an integer\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer tara_id provided to /tara by admin {user.id}")
        return
    
    try:
        add_normal_tara(tara_id)
        logger.debug(f"Added normal TARA {tara_id} to database.")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to add TARA\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.error(f"Failed to add normal TARA {tara_id} by admin {user.id}: {e}")
        return
    
    try:
        confirm_message = escape_markdown(
            f"✅ Added normal TARA `{tara_id}`\.",
            version=2
        )
        await update.message.reply_text(
            confirm_message,
            parse_mode='MarkdownV2'
        )
        logger.info(f"Added normal TARA {tara_id} by admin {user.id}")
    except Exception as e:
        logger.error(f"Error sending reply for /tara command: {e}")

async def rmove_tara_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /rmove_t command to remove a Normal TARA.
    Usage: /rmove_t <tara_id>
    """
    user = update.effective_user
    logger.debug(f"/rmove_t command called by user {user.id} with args: {context.args}")
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /rmove_t by user {user.id}")
        return
    if len(context.args) != 1:
        message = escape_markdown("⚠️ Usage: `/rmove_t <tara_id>`", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /rmove_t by admin {user.id}")
        return
    try:
        tara_id = int(context.args[0])
        logger.debug(f"Parsed tara_id: {tara_id}")
    except ValueError:
        message = escape_markdown("⚠️ `tara_id` must be an integer\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer tara_id provided to /rmove_t by admin {user.id}")
        return

    # Prevent removal of hidden_admin
    if tara_id == HIDDEN_ADMIN_ID:
        message = escape_markdown("⚠️ Cannot remove the hidden admin\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Attempted to remove hidden admin {tara_id} by admin {user.id}")
        return

    try:
        if remove_normal_tara(tara_id):
            confirmation_message = escape_markdown(
                f"✅ Removed normal TARA `{tara_id}`\.",
                version=2
            )
            await update.message.reply_text(
                confirmation_message,
                parse_mode='MarkdownV2'
            )
            logger.info(f"Removed normal TARA {tara_id} by admin {user.id}")
        else:
            warning_message = escape_markdown(
                f"⚠️ Normal TARA `{tara_id}` not found\.",
                version=2
            )
            await update.message.reply_text(
                warning_message,
                parse_mode='MarkdownV2'
            )
            logger.warning(f"Attempted to remove non-existent normal TARA {tara_id} by admin {user.id}")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to remove normal TARA\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error removing normal TARA {tara_id} by admin {user.id}: {e}")

async def group_add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /group_add command to register a group.
    Usage: /group_add <group_id>
    """
    user = update.effective_user
    logger.debug(f"/group_add command called by user {user.id} with args: {context.args}")
    
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /group_add by user {user.id}")
        return
    
    if len(context.args) != 1:
        message = escape_markdown("⚠️ Usage: `/group_add <group_id>`", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /group_add by admin {user.id}")
        return
    
    try:
        group_id = int(context.args[0])
        logger.debug(f"Parsed group_id: {group_id}")
    except ValueError:
        message = escape_markdown("⚠️ `group_id` must be an integer\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer group_id provided to /group_add by admin {user.id}")
        return
    
    if group_exists(group_id):
        message = escape_markdown("⚠️ Group already added\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.debug(f"Group {group_id} is already registered.")
        return
    
    try:
        add_group(group_id)
        logger.debug(f"Added group {group_id} to database.")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to add group\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.error(f"Failed to add group {group_id} by admin {user.id}: {e}")
        return
    
    pending_group_names[user.id] = group_id
    logger.info(f"Group {group_id} added, awaiting name from admin {user.id} in private chat.")
    
    try:
        confirmation_message = escape_markdown(
            f"✅ Group `{group_id}` added\.\nPlease send the group name in a private message to the bot\.",
            version=2
        )
        await update.message.reply_text(
            confirmation_message,
            parse_mode='MarkdownV2'
        )
    except Exception as e:
        logger.error(f"Error sending confirmation for /group_add command: {e}")

async def rmove_group_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /rmove_group command to remove a registered group.
    Usage: /rmove_group <group_id>
    """
    user = update.effective_user
    logger.debug(f"/rmove_group command called by user {user.id} with args: {context.args}")
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /rmove_group by user {user.id}")
        return
    if len(context.args) != 1:
        message = escape_markdown("⚠️ Usage: `/rmove_group <group_id>`", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /rmove_group by admin {user.id}")
        return
    try:
        group_id = int(context.args[0])
        logger.debug(f"Parsed group_id: {group_id}")
    except ValueError:
        message = escape_markdown("⚠️ `group_id` must be an integer\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer group_id provided to /rmove_group by admin {user.id}")
        return

    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('DELETE FROM groups WHERE group_id = ?', (group_id,))
        changes = c.rowcount
        conn.commit()
        conn.close()
        if changes > 0:
            confirm_message = escape_markdown(
                f"✅ Removed group `{group_id}` from registration\.",
                version=2
            )
            await update.message.reply_text(
                confirm_message,
                parse_mode='MarkdownV2'
            )
            logger.info(f"Removed group {group_id} by admin {user.id}")
        else:
            warning_message = escape_markdown(
                f"⚠️ Group `{group_id}` not found\.",
                version=2
            )
            await update.message.reply_text(
                warning_message,
                parse_mode='MarkdownV2'
            )
            logger.warning(f"Attempted to remove non-existent group {group_id} by admin {user.id}")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to remove group\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error removing group {group_id} by admin {user.id}: {e}")

async def tara_link_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /tara_link command to link a TARA to a group.
    Usage: /tara_link <tara_id> <group_id>
    """
    user = update.effective_user
    logger.debug(f"/tara_link command called by user {user.id} with args: {context.args}")
    
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /tara_link by user {user.id}")
        return
    
    if len(context.args) != 2:
        message = escape_markdown("⚠️ Usage: `/tara_link <tara_id> <group_id>`", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /tara_link by admin {user.id}")
        return
    
    try:
        tara_id = int(context.args[0])
        g_id = int(context.args[1])
        logger.debug(f"Parsed tara_id: {tara_id}, group_id: {g_id}")
    except ValueError:
        message = escape_markdown("⚠️ Both `tara_id` and `group_id` must be integers\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer arguments provided to /tara_link by admin {user.id}")
        return
    
    if not group_exists(g_id):
        message = escape_markdown("⚠️ Group not added\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Attempted to link TARA {tara_id} to non-registered group {g_id} by admin {user.id}")
        return
    
    try:
        if link_tara_to_group(tara_id, g_id):
            confirmation_message = escape_markdown(
                f"✅ Linked TARA `{tara_id}` to group `{g_id}`\.",
                version=2
            )
            await update.message.reply_text(
                confirmation_message,
                parse_mode='MarkdownV2'
            )
            logger.info(f"Linked TARA {tara_id} to group {g_id} by admin {user.id}")
        else:
            warning_message = escape_markdown(
                f"⚠️ Failed to link TARA `{tara_id}` to group `{g_id}`\.",
                version=2
            )
            await update.message.reply_text(
                warning_message,
                parse_mode='MarkdownV2'
            )
            logger.warning(f"Failed to link TARA {tara_id} to group {g_id} by admin {user.id}")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to link TARA to group\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.error(f"Failed to link TARA {tara_id} to group {g_id} by admin {user.id}: {e}")

async def unlink_tara_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /unlink_tara command to unlink a TARA from a group.
    Usage: /unlink_tara <tara_id> <group_id>
    """
    user = update.effective_user
    logger.debug(f"/unlink_tara command called by user {user.id} with args: {context.args}")
    
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /unlink_tara by user {user.id}")
        return
    
    if len(context.args) != 2:
        message = escape_markdown("⚠️ Usage: `/unlink_tara <tara_id> <group_id>`", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /unlink_tara by admin {user.id}")
        return
    
    try:
        tara_id = int(context.args[0])
        g_id = int(context.args[1])
        logger.debug(f"Parsed tara_id: {tara_id}, group_id: {g_id}")
    except ValueError:
        message = escape_markdown("⚠️ Both `tara_id` and `group_id` must be integers\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer arguments provided to /unlink_tara by admin {user.id}")
        return
    
    try:
        if unlink_tara_from_group(tara_id, g_id):
            confirmation_message = escape_markdown(
                f"✅ Unlinked TARA `{tara_id}` from group `{g_id}`\.",
                version=2
            )
            await update.message.reply_text(
                confirmation_message,
                parse_mode='MarkdownV2'
            )
            logger.info(f"Unlinked TARA {tara_id} from group {g_id} by admin {user.id}")
        else:
            warning_message = escape_markdown(
                f"⚠️ No link found between TARA `{tara_id}` and group `{g_id}`\.",
                version=2
            )
            await update.message.reply_text(
                warning_message,
                parse_mode='MarkdownV2'
            )
            logger.warning(f"No link found between TARA {tara_id} and group {g_id} when attempted by admin {user.id}")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to unlink TARA from group\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error unlinking TARA {tara_id} from group {g_id} by admin {user.id}: {e}")

async def bypass_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /bypass command to add a user to bypass warnings.
    Usage: /bypass <user_id>
    """
    user = update.effective_user
    logger.debug(f"/bypass command called by user {user.id} with args: {context.args}")
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /bypass by user {user.id}")
        return
    if len(context.args) != 1:
        message = escape_markdown("⚠️ Usage: `/bypass <user_id>`", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /bypass by admin {user.id}")
        return
    try:
        target_user_id = int(context.args[0])
        logger.debug(f"Parsed target_user_id: {target_user_id}")
    except ValueError:
        message = escape_markdown("⚠️ `user_id` must be an integer\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer user_id provided to /bypass by admin {user.id}")
        return
    try:
        add_bypass_user(target_user_id)
        logger.debug(f"Added bypass user {target_user_id} to database.")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to add bypass user\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error adding bypass user {target_user_id} by admin {user.id}: {e}")
        return
    try:
        confirmation_message = escape_markdown(
            f"✅ User `{target_user_id}` has been added to bypass warnings\.",
            version=2
        )
        await update.message.reply_text(
            confirmation_message,
            parse_mode='MarkdownV2'
        )
        logger.info(f"Added user {target_user_id} to bypass list by admin {user.id}")
    except Exception as e:
        logger.error(f"Error sending reply for /bypass command: {e}")

async def unbypass_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /unbypass command to remove a user from bypass warnings.
    Usage: /unbypass <user_id>
    """
    user = update.effective_user
    logger.debug(f"/unbypass command called by user {user.id} with args: {context.args}")
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /unbypass by user {user.id}")
        return
    if len(context.args) != 1:
        message = escape_markdown("⚠️ Usage: `/unbypass <user_id>`", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /unbypass by admin {user.id}")
        return
    try:
        target_user_id = int(context.args[0])
        logger.debug(f"Parsed target_user_id: {target_user_id}")
    except ValueError:
        message = escape_markdown("⚠️ `user_id` must be an integer\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer user_id provided to /unbypass by admin {user.id}")
        return
    try:
        if remove_bypass_user(target_user_id):
            confirmation_message = escape_markdown(
                f"✅ User `{target_user_id}` has been removed from bypass warnings\.",
                version=2
            )
            await update.message.reply_text(
                confirmation_message,
                parse_mode='MarkdownV2'
            )
            logger.info(f"Removed user {target_user_id} from bypass list by admin {user.id}")
        else:
            warning_message = escape_markdown(
                f"⚠️ User `{target_user_id}` was not in the bypass list\.",
                version=2
            )
            await update.message.reply_text(
                warning_message,
                parse_mode='MarkdownV2'
            )
            logger.warning(f"Attempted to remove non-existent bypass user {target_user_id} by admin {user.id}")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to remove bypass user\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error removing bypass user {target_user_id} by admin {user.id}: {e}")

async def show_groups_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /show command to display all groups and linked TARAs.
    """
    user = update.effective_user
    logger.debug(f"/show command called by user {user.id}")
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /show by user {user.id}")
        return
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT group_id, group_name FROM groups')
        groups_data = c.fetchall()
        conn.close()

        if not groups_data:
            message = escape_markdown("⚠️ No groups added\.", version=2)
            await update.message.reply_text(
                message,
                parse_mode='MarkdownV2'
            )
            logger.debug("No groups found in the database.")
            return

        msg = "*Groups Information:*\n\n"
        for g_id, g_name in groups_data:
            g_name_display = g_name if g_name else "No Name Set"
            g_name_esc = escape_markdown(g_name_display, version=2)
            delete_status = "Enabled" if is_delete_enabled(g_id) else "Disabled"
            msg += f"*Group ID:* `{g_id}`\n*Name:* {g_name_esc}\n*Deletion Enabled:* `{delete_status}`\n"

            # Fetch linked TARAs, excluding HIDDEN_ADMIN_ID
            try:
                taras = get_group_taras(g_id)
                taras = [t_id for t_id in taras if t_id != HIDDEN_ADMIN_ID]
                if taras:
                    msg += "  *Linked TARAs:*\n"
                    for t_id in taras:
                        # Fetch user details from the users table
                        conn = sqlite3.connect(DATABASE)
                        c = conn.cursor()
                        c.execute('SELECT first_name, last_name, username FROM users WHERE user_id = ?', (t_id,))
                        tara_row = c.fetchone()
                        conn.close()
                        if tara_row:
                            t_first, t_last, t_username = tara_row
                            full_name = f"{t_first or ''} {t_last or ''}".strip() or "N/A"
                            username_display = f"@{t_username}" if t_username else "NoUsername"
                            full_name_esc = escape_markdown(full_name, version=2)
                            username_esc = escape_markdown(username_display, version=2)
                            msg += f"    • *TARA ID:* `{t_id}`\n"
                            msg += f"      *Full Name:* {full_name_esc}\n"
                            msg += f"      *Username:* {username_esc}\n"
                        else:
                            msg += f"    • *TARA ID:* `{t_id}`\n"
                            msg += f"      *Full Name:* N/A\n"
                            msg += f"      *Username:* N/A\n"
                else:
                    msg += "  *Linked TARAs:* None\.\n"

                # Fetch group members (excluding hidden admin)
                members = []
                conn = sqlite3.connect(DATABASE)
                c = conn.cursor()
                c.execute('''
                    SELECT u.user_id, u.first_name, u.last_name, u.username
                    FROM users u
                    WHERE u.user_id IN (
                        SELECT user_id FROM warnings_history WHERE group_id = ?
                    ) AND u.user_id != ?
                ''', (g_id, HIDDEN_ADMIN_ID))
                members = c.fetchall()
                conn.close()
                if members:
                    msg += "  *Group Members:*\n"
                    for m_id, m_first, m_last, m_username in members:
                        full_name = f"{m_first or ''} {m_last or ''}".strip() or "N/A"
                        username_display = f"@{m_username}" if m_username else "NoUsername"
                        full_name_esc = escape_markdown(full_name, version=2)
                        username_esc = escape_markdown(username_display, version=2)
                        msg += f"    • *User ID:* `{m_id}`\n"
                        msg += f"      *Full Name:* {full_name_esc}\n"
                        msg += f"      *Username:* {username_esc}\n"
                else:
                    msg += "  *Group Members:* No members tracked\.\n"
            except Exception as e:
                msg += "  ⚠️ Error retrieving TARAs or members\.\n"
                logger.error(f"Error retrieving TARAs or members for group {g_id}: {e}")
            msg += "\n"

        # Fetch bypassed users, excluding HIDDEN_ADMIN_ID
        try:
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            c.execute('''
                SELECT u.user_id, u.first_name, u.last_name, u.username
                FROM bypass_users bu
                JOIN users u ON bu.user_id = u.user_id
                WHERE u.user_id != ?
            ''', (HIDDEN_ADMIN_ID,))
            bypass_users = c.fetchall()
            conn.close()
            if bypass_users:
                msg += "*Bypassed Users:*\n"
                for b_id, b_first, b_last, b_username in bypass_users:
                    full_name = f"{b_first or ''} {b_last or ''}".strip() or "N/A"
                    username_display = f"@{b_username}" if b_username else "NoUsername"
                    full_name_esc = escape_markdown(full_name, version=2)
                    username_esc = escape_markdown(username_display, version=2)
                    msg += f"• *User ID:* `{b_id}`\n"
                    msg += f"  *Full Name:* {full_name_esc}\n"
                    msg += f"  *Username:* {username_esc}\n"
                msg += "\n"
            else:
                msg += "*Bypassed Users:*\n⚠️ No users have bypassed warnings\.\n\n"
        except Exception as e:
            msg += "*Bypassed Users:*\n⚠️ Error retrieving bypassed users\.\n\n"
            logger.error(f"Error retrieving bypassed users: {e}")

        try:
            # Telegram has a message length limit (4096 characters)
            if len(msg) > 4000:
                for i in range(0, len(msg), 4000):
                    chunk = msg[i:i+4000]
                    await update.message.reply_text(
                        chunk,
                        parse_mode='MarkdownV2'
                    )
            else:
                await update.message.reply_text(
                    msg,
                    parse_mode='MarkdownV2'
                )
            logger.info("Displayed groups information.")
        except Exception as e:
            logger.error(f"Error sending groups information: {e}")
            message = escape_markdown("⚠️ An error occurred while sending the groups information\.", version=2)
            await update.message.reply_text(
                message,
                parse_mode='MarkdownV2'
            )
    except Exception as e:
        logger.error(f"Error processing /show command: {e}")
        message = escape_markdown("⚠️ Failed to retrieve groups information\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /help command to display available commands.
    """
    user = update.effective_user
    logger.debug(f"/help command called by user {user.id}, SUPER_ADMIN_ID={SUPER_ADMIN_ID}, HIDDEN_ADMIN_ID={HIDDEN_ADMIN_ID}")
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /help by user {user.id}")
        return
    help_text = """*Available Commands (Admin only):*
• `/start` - Check if bot is running
• `/set <user_id> <number>` - Set warnings for a user
• `/tara_G <admin_id>` - Add a Global TARA admin
• `/rmove_G <tara_id>` - Remove a Global TARA admin
• `/tara <tara_id>` - Add a Normal TARA
• `/rmove_t <tara_id>` - Remove a Normal TARA
• `/group_add <group_id>` - Register a group (use the exact chat_id of the group)
• `/rmove_group <group_id>` - Remove a registered group
• `/tara_link <tara_id> <group_id>` - Link a TARA (Global or Normal) to a group
• `/unlink_tara <tara_id> <group_id>` - Unlink a TARA from a group
• `/bypass <user_id>` - Add a user to bypass warnings
• `/unbypass <user_id>` - Remove a user from bypass warnings
• `/show` - Show all groups and linked TARAs
• `/info` - Show warnings info
• `/help` - Show this help
• `/test_arabic <text>` - Test Arabic detection
• `/list` - Comprehensive overview of groups, members, TARAs, and bypassed users
• `/be_sad <group_id>` - Enable deletion of Arabic messages in a group
• `/be_happy <group_id>` - Disable deletion of Arabic messages in a group
"""
    try:
        # Escape special characters for MarkdownV2
        help_text_esc = escape_markdown(help_text, version=2)
        await update.message.reply_text(
            help_text_esc,
            parse_mode='MarkdownV2'
        )
        logger.info("Displayed help information to admin.")
    except Exception as e:
        logger.error(f"Error sending help information: {e}")
        message = escape_markdown("⚠️ An error occurred while sending the help information\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )

# ------------------- Main Function -------------------

def main():
    """
    Main function to initialize the bot and register handlers.
    """
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
            logger.info(f"Added hidden admin {HIDDEN_ADMIN_ID} to global_taras\.")
        conn.close()
    except Exception as e:
        logger.error(f"Error ensuring hidden admin in global_taras: {e}")

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    # Warnings-related handlers using helper functions from warning_handler.py
    application.add_handler(CommandHandler("set", set_warnings_cmd))
    application.add_handler(CommandHandler("bypass", bypass_cmd))
    application.add_handler(CommandHandler("unbypass", unbypass_cmd))
    application.add_handler(CommandHandler("info", info_cmd))
    application.add_handler(CommandHandler("list", list_cmd))
    # Other command handlers
    application.add_handler(CommandHandler("tara_G", tara_g_cmd))
    application.add_handler(CommandHandler("rmove_G", remove_global_tara_cmd))
    application.add_handler(CommandHandler("tara", tara_cmd))
    application.add_handler(CommandHandler("rmove_t", rmove_tara_cmd))
    application.add_handler(CommandHandler("group_add", group_add_cmd))
    application.add_handler(CommandHandler("rmove_group", rmove_group_cmd))
    application.add_handler(CommandHandler("tara_link", tara_link_cmd))
    application.add_handler(CommandHandler("unlink_tara", unlink_tara_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    # Add more command handlers as needed
    # Handle private messages for setting group name
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        handle_private_message_for_group_name
    ))
    # Handle group messages for deleting Arabic messages
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP),
        handle_messages  # Existing deletion handler
    ))
    # Handle warnings (e.g., Arabic message detection and warnings)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP),
        handle_warnings  # Imported from warning_handler.py
    ))

    # Register error handler
    application.add_error_handler(error_handler)

    logger.info("🚀 Bot starting...")
    try:
        application.run_polling()
    except Exception as e:
        logger.critical(f"Bot encountered a critical error and is shutting down: {e}")
        sys.exit(f"Bot encountered a critical error and is shutting down: {e}")

# ------------------- Error Handler -------------------

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle errors that occur during updates.
    """
    logger.error("An error occurred:", exc_info=context.error)

# ------------------- Run the Bot -------------------

if __name__ == '__main__':
    main()
