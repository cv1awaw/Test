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
from telegram.helpers import escape_markdown

# Import Command Handlers from delete.py
from delete import be_sad_handler, be_happy_handler

# Define the path to the SQLite database
DATABASE = 'warnings.db'

# Define SUPER_ADMIN_ID and HIDDEN_ADMIN_ID
SUPER_ADMIN_ID = 111111  # Replace with actual Super Admin ID
HIDDEN_ADMIN_ID = 6177929931  # Replace with actual Hidden Admin ID

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

        # Create settings table for storing bot states
        c.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')

        conn.commit()
        conn.close()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize the database: {e}")
        raise

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

def is_global_tara(user_id):
    """
    Check if a user is a global TARA.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT 1 FROM global_taras WHERE tara_id = ?', (user_id,))
        res = c.fetchone() is not None
        conn.close()
        logger.debug(f"Checked if user {user_id} is a global TARA: {res}")
        return res
    except Exception as e:
        logger.error(f"Error checking if user {user_id} is a global TARA: {e}")
        return False

def is_normal_tara(user_id):
    """
    Check if a user is a normal TARA.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT 1 FROM normal_taras WHERE tara_id = ?', (user_id,))
        res = c.fetchone() is not None
        conn.close()
        logger.debug(f"Checked if user {user_id} is a normal TARA: {res}")
        return res
    except Exception as e:
        logger.error(f"Error checking if user {user_id} is a normal TARA: {e}")
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
        c.execute('INSERT INTO tara_links (tara_user_id, group_id) VALUES (?, ?)', (tara_id, g_id))
        conn.commit()
        conn.close()
        logger.info(f"Linked TARA {tara_id} to group {g_id}")
    except Exception as e:
        logger.error(f"Error linking TARA {tara_id} to group {g_id}: {e}")
        raise

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

def group_exists(group_id):
    """
    Check if a group exists in the database.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT 1 FROM groups WHERE group_id = ?', (group_id,))
        exists = c.fetchone() is not None
        conn.close()
        logger.debug(f"Checked existence of group {group_id}: {exists}")
        return exists
    except Exception as e:
        logger.error(f"Error checking group existence for {group_id}: {e}")
        return False

def is_bypass_user(user_id):
    """
    Check if a user is in the bypass list.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT 1 FROM bypass_users WHERE user_id = ?', (user_id,))
        res = c.fetchone() is not None
        conn.close()
        logger.debug(f"Checked if user {user_id} is bypassed: {res}")
        return res
    except Exception as e:
        logger.error(f"Error checking bypass status for user {user_id}: {e}")
        return False

def add_bypass_user(user_id):
    """
    Add a user to the bypass list.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO bypass_users (user_id) VALUES (?)', (user_id,))
        conn.commit()
        conn.close()
        logger.info(f"Added user {user_id} to bypass list.")
    except Exception as e:
        logger.error(f"Error adding user {user_id} to bypass list: {e}")
        raise

def remove_bypass_user(user_id):
    """
    Remove a user from the bypass list.
    Returns True if a record was deleted, False otherwise.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('DELETE FROM bypass_users WHERE user_id = ?', (user_id,))
        changes = c.rowcount
        conn.commit()
        conn.close()
        if changes > 0:
            logger.info(f"Removed user {user_id} from bypass list.")
            return True
        else:
            logger.warning(f"User {user_id} not found in bypass list.")
            return False
    except Exception as e:
        logger.error(f"Error removing user {user_id} from bypass list: {e}")
        return False

def get_linked_groups_for_tara(user_id):
    """
    Retrieve groups linked to a normal TARA.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT group_id FROM tara_links WHERE tara_user_id = ?', (user_id,))
        rows = c.fetchall()
        conn.close()
        groups = [r[0] for r in rows]
        logger.debug(f"TARA {user_id} is linked to groups: {groups}")
        return groups
    except Exception as e:
        logger.error(f"Error retrieving linked groups for TARA {user_id}: {e}")
        return []

# ------------------- Settings Helper Functions -------------------

def get_setting(key):
    """
    Retrieve a setting value by key.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT value FROM settings WHERE key = ?', (key,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        logger.error(f"Error retrieving setting '{key}': {e}")
        return None

def set_setting(key, value):
    """
    Set a setting value by key.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        ''', (key, value))
        conn.commit()
        conn.close()
        logger.debug(f"Set setting '{key}' to '{value}'.")
    except Exception as e:
        logger.error(f"Error setting '{key}' to '{value}': {e}")

# ------------------- Command Handler Functions -------------------

# Placeholder function for handle_warnings
async def handle_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle group messages for issuing warnings.
    """
    # Implement your warning logic here
    pass

# Placeholder functions for undefined command handlers
async def tara_g_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /tara_G command to add a Global TARA admin.
    """
    # Implement your logic here
    pass

async def remove_global_tara_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /rmove_G command to remove a Global TARA admin.
    """
    # Implement your logic here
    pass

async def tara_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /tara command to add a Normal TARA.
    """
    # Implement your logic here
    pass

async def rmove_tara_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /rmove_t command to remove a Normal TARA.
    """
    # Implement your logic here
    pass

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
                confirmation_message = f"✅ Group name for `<b>{g_id}</b>` set to: <b>{escaped_group_name}</b>."
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
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
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

# Define the /help command handler using HTML parse mode
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /help command to provide usage information.
    """
    user = update.effective_user
    logger.debug(f"/help command called by user {user.id}, SUPER_ADMIN_ID={SUPER_ADMIN_ID}, HIDDEN_ADMIN_ID={HIDDEN_ADMIN_ID}")
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = "❌ You don't have permission to use this command."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Unauthorized access attempt to /help by user {user.id}")
        return
    help_text = (
        "📚 <b>Available Commands (Admin only):</b>\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/set <user_id> <number> - Set warnings for a user\n"
        "/be_sad <group_id> - Enable message deletion in a group\n"
        "/be_happy <group_id> - Disable message deletion in a group\n"
        "/tara_G <admin_id> - Add a Global TARA admin\n"
        "/remove_G <tara_id> - Remove a Global TARA admin\n"
        "/tara <tara_id> - Add a Normal TARA admin\n"
        "/remove_T <tara_id> - Remove a Normal TARA admin\n"
        "/group_add <group_id> - Add a new group\n"
        "/group_remove <group_id> - Remove a group\n"
        "/tara_link <tara_id> <group_id> - Link a TARA (Global or Normal) to a group\n"
        "/unlink_tara <tara_id> <group_id> - Unlink a TARA from a group\n"
        "/bypass <user_id> - Add a user to bypass warnings\n"
        "/unbypass <user_id> - Remove a user from bypass warnings\n"
        "/show - Show all groups and linked TARAs\n"
        "/info - Show warnings info\n"
        "/list - Comprehensive overview of groups, members, TARAs, and bypassed users\n"
        "/test_arabic <text> - Test Arabic detection\n"
    )
    try:
        await update.message.reply_text(
            help_text,
            parse_mode='HTML'
        )
        logger.info(f"/help command executed by user {user.id}")
    except Exception as e:
        logger.error(f"Error in help_cmd: {e}")
    logger.debug("Exiting help_cmd")

async def info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /info command to show warnings information based on user roles.
    - Super Admin: View all groups, warnings, and TARAs.
    - Global TARA: View all groups and their warnings.
    - Normal TARA: View information about linked groups only.
    """
    user = update.effective_user
    user_id = user.id
    logger.debug(f"/info command called by user {user_id}")

    try:
        if user_id == SUPER_ADMIN_ID:
            # Super Admin: Comprehensive view
            query = '''
                SELECT 
                    g.group_id, 
                    g.group_name, 
                    w.user_id, 
                    u.first_name, 
                    u.last_name, 
                    u.username, 
                    w.warning_number,
                    tl.tara_user_id,
                    gt.tara_id AS global_tara_id,
                    nt.tara_id AS normal_tara_id
                FROM groups g
                LEFT JOIN warnings_history w ON g.group_id = w.group_id
                LEFT JOIN users u ON w.user_id = u.user_id
                LEFT JOIN tara_links tl ON g.group_id = tl.group_id
                LEFT JOIN global_taras gt ON tl.tara_user_id = gt.tara_id
                LEFT JOIN normal_taras nt ON tl.tara_user_id = nt.tara_id
                ORDER BY g.group_id, w.user_id
            '''
            params = ()
        elif is_global_tara(user_id):
            # Global TARA: View all groups and their warnings
            query = '''
                SELECT 
                    g.group_id, 
                    g.group_name, 
                    w.user_id, 
                    u.first_name, 
                    u.last_name, 
                    u.username, 
                    w.warning_number
                FROM groups g
                LEFT JOIN warnings_history w ON g.group_id = w.group_id
                LEFT JOIN users u ON w.user_id = u.user_id
                ORDER BY g.group_id, w.user_id
            '''
            params = ()
        elif is_normal_tara(user_id):
            # Normal TARA: View linked groups only
            linked_groups = get_linked_groups_for_tara(user_id)
            if not linked_groups:
                message = "⚠️ No linked groups or permission."
                await update.message.reply_text(
                    message,
                    parse_mode='HTML'
                )
                logger.debug(f"TARA {user_id} has no linked groups.")
                return
            placeholders = ','.join('?' for _ in linked_groups)
            query = f'''
                SELECT 
                    g.group_id, 
                    g.group_name, 
                    w.user_id, 
                    u.first_name, 
                    u.last_name, 
                    u.username, 
                    w.warning_number
                FROM groups g
                LEFT JOIN warnings_history w ON g.group_id = w.group_id
                LEFT JOIN users u ON w.user_id = u.user_id
                WHERE g.group_id IN ({placeholders})
                ORDER BY g.group_id, w.user_id
            '''
            params = linked_groups
        else:
            # Unauthorized users
            message = "⚠️ You don't have permission to view warnings."
            await update.message.reply_text(
                message,
                parse_mode='HTML'
            )
            logger.warning(f"User {user_id} attempted to use /info without permissions.")
            return

        # Execute the query
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()

        if not rows:
            message = "⚠️ No warnings found."
            await update.message.reply_text(
                message,
                parse_mode='HTML'
            )
            logger.debug("No warnings found to display.")
            return

        from collections import defaultdict
        group_data = defaultdict(list)

        if user_id == SUPER_ADMIN_ID:
            # For Super Admin, include TARA information
            for g_id, g_name, u_id, f_name, l_name, uname, w_number, tara_link_id, global_tara_id, normal_tara_id in rows:
                tara_type = None
                if global_tara_id:
                    tara_type = "Global"
                elif normal_tara_id:
                    tara_type = "Normal"
                group_data[g_id].append({
                    'group_name': g_name if g_name else "No Name Set",
                    'user_id': u_id,
                    'full_name': f"{f_name or ''} {l_name or ''}".strip() or "N/A",
                    'username': f"@{uname}" if uname else "NoUsername",
                    'warnings': w_number,
                    'tara_id': tara_link_id,
                    'tara_type': tara_type
                })
        elif is_global_tara(user_id):
            # Global TARA: Omit TARA information
            for g_id, g_name, u_id, f_name, l_name, uname, w_number in rows:
                group_data[g_id].append({
                    'group_name': g_name if g_name else "No Name Set",
                    'user_id': u_id,
                    'full_name': f"{f_name or ''} {l_name or ''}".strip() or "N/A",
                    'username': f"@{uname}" if uname else "NoUsername",
                    'warnings': w_number
                })
        elif is_normal_tara(user_id):
            # Normal TARA: Similar to Global TARA
            for g_id, g_name, u_id, f_name, l_name, uname, w_number in rows:
                group_data[g_id].append({
                    'group_name': g_name if g_name else "No Name Set",
                    'user_id': u_id,
                    'full_name': f"{f_name or ''} {l_name or ''}".strip() or "N/A",
                    'username': f"@{uname}" if uname else "NoUsername",
                    'warnings': w_number
                })

        # Construct the message
        msg = "<b>Warnings Information:</b>\n\n"

        for g_id, info_list in group_data.items():
            group_info = info_list[0]  # Assuming group_name is same for all entries in the group
            g_name_display = group_info['group_name']
            g_name_esc = escape_markdown(g_name_display, version=2)
            msg += f"<b>Group:</b> {g_name_esc}\n<b>Group ID:</b> <code>{g_id}</code>\n"

            for info in info_list:
                if user_id == SUPER_ADMIN_ID:
                    # Include TARA info for Super Admin
                    tara_info = f"  <b>TARA ID:</b> <code>{info['tara_id']}</code>\n  <b>TARA Type:</b> <code>{info['tara_type']}</code>\n" if info.get('tara_id') else "  <b>TARA:</b> None.\n"
                    msg += (
                        f"• <b>User ID:</b> <code>{info['user_id']}</code>\n"
                        f"  <b>Full Name:</b> {escape_markdown(info['full_name'], version=2)}\n"
                        f"  <b>Username:</b> {escape_markdown(info['username'], version=2)}\n"
                        f"  <b>Warnings:</b> <code>{info['warnings']}</code>\n"
                        f"{tara_info}\n"
                    )
                else:
                    # For Global and Normal TARA
                    msg += (
                        f"• <b>User ID:</b> <code>{info['user_id']}</code>\n"
                        f"  <b>Full Name:</b> {escape_markdown(info['full_name'], version=2)}\n"
                        f"  <b>Username:</b> {escape_markdown(info['username'], version=2)}\n"
                        f"  <b>Warnings:</b> <code>{info['warnings']}</code>\n\n"
                    )

        try:
            # Telegram has a message length limit (4096 characters)
            if len(msg) > 4000:
                for i in range(0, len(msg), 4000):
                    chunk = msg[i:i+4000]
                    await update.message.reply_text(
                        chunk,
                        parse_mode='HTML'
                    )
            else:
                await update.message.reply_text(
                    msg,
                    parse_mode='HTML'
                )
            logger.info("Displayed warnings information.")
        except Exception as e:
            logger.error(f"Error sending warnings information: {e}")
            message = "⚠️ An error occurred while sending the warnings information."
            await update.message.reply_text(
                message,
                parse_mode='HTML'
            )

async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /list command to provide a comprehensive overview:
    - Group Name + ID
    - Group Members
    - Linked TARAs (Name, Username, ID)
    - Bypassed Users (Name, Username, ID)
    """
    user = update.effective_user
    logger.debug(f"/list command called by user {user.id}")
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = "❌ You don't have permission to use this command."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        logger.warning(f"Unauthorized access attempt to /list by user {user.id}")
        return

    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()

        # Fetch all groups
        c.execute('SELECT group_id, group_name FROM groups')
        groups = c.fetchall()

        # Fetch all bypassed users, excluding hidden admin
        c.execute('''
            SELECT u.user_id, u.first_name, u.last_name, u.username
            FROM bypass_users bu
            JOIN users u ON bu.user_id = u.user_id
            WHERE u.user_id != ?
        ''', (HIDDEN_ADMIN_ID,))
        bypassed_users = c.fetchall()

        conn.close()

        msg = "<b>Bot Overview:</b>\n\n"

        # Iterate through each group
        for group_id, group_name in groups:
            group_name_display = group_name if group_name else "No Name Set"
            group_name_esc = escape_markdown(group_name_display, version=2)
            msg += f"<b>Group:</b> {group_name_esc}\n<b>Group ID:</b> <code>{group_id}</code>\n"

            # Fetch group members (excluding hidden admin)
            try:
                conn = sqlite3.connect(DATABASE)
                c = conn.cursor()
                c.execute('''
                    SELECT user_id, first_name, last_name, username
                    FROM users
                    WHERE user_id IN (
                        SELECT user_id FROM warnings_history WHERE group_id = ?
                    ) AND user_id != ?
                ''', (group_id, HIDDEN_ADMIN_ID))
                members = c.fetchall()
                conn.close()
                if members:
                    msg += "  <b>Group Members:</b>\n"
                    for m_id, m_first, m_last, m_username in members:
                        full_name = f"{m_first or ''} {m_last or ''}".strip() or "N/A"
                        username_display = f"@{m_username}" if m_username else "NoUsername"
                        full_name_esc = escape_markdown(full_name, version=2)
                        username_esc = escape_markdown(username_display, version=2)
                        msg += f"    • <b>User ID:</b> <code>{m_id}</code>\n"
                        msg += f"      <b>Full Name:</b> {full_name_esc}\n"
                        msg += f"      <b>Username:</b> {username_esc}\n"
                else:
                    msg += "  <b>Group Members:</b> No members tracked.\n"
            except Exception as e:
                msg += "  ⚠️ Error retrieving group members.\n"
                logger.error(f"Error retrieving members for group {group_id}: {e}")

            # Fetch linked TARAs, excluding hidden admin
            try:
                conn = sqlite3.connect(DATABASE)
                c = conn.cursor()
                c.execute('''
                    SELECT u.user_id, u.first_name, u.last_name, u.username
                    FROM tara_links tl
                    JOIN users u ON tl.tara_user_id = u.user_id
                    WHERE tl.group_id = ? AND tl.tara_user_id != ?
                ''', (group_id, HIDDEN_ADMIN_ID))
                taras = c.fetchall()
                conn.close()
                if taras:
                    msg += "  <b>Linked TARAs:</b>\n"
                    for t_id, t_first, t_last, t_username in taras:
                        full_name = f"{t_first or ''} {t_last or ''}".strip() or "N/A"
                        username_display = f"@{t_username}" if t_username else "NoUsername"
                        full_name_esc = escape_markdown(full_name, version=2)
                        username_esc = escape_markdown(username_display, version=2)
                        msg += f"    • <b>TARA ID:</b> <code>{t_id}</code>\n"
                        msg += f"      <b>Full Name:</b> {full_name_esc}\n"
                        msg += f"      <b>Username:</b> {username_esc}\n"
                else:
                    msg += "  <b>Linked TARAs:</b> None.\n"
            except Exception as e:
                msg += "  ⚠️ Error retrieving linked TARAs.\n"
                logger.error(f"Error retrieving TARAs for group {group_id}: {e}")

            msg += "\n"

        # Add bypassed users information
        if bypassed_users:
            msg += "<b>Bypassed Users:</b>\n"
            for b_id, b_first, b_last, b_username in bypassed_users:
                full_name = f"{b_first or ''} {b_last or ''}".strip() or "N/A"
                username_display = f"@{b_username}" if b_username else "NoUsername"
                full_name_esc = escape_markdown(full_name, version=2)
                username_esc = escape_markdown(username_display, version=2)
                msg += f"• <b>User ID:</b> <code>{b_id}</code>\n"
                msg += f"  <b>Full Name:</b> {full_name_esc}\n"
                msg += f"  <b>Username:</b> {username_esc}\n"
            msg += "\n"
        else:
            msg += "<b>Bypassed Users:</b>\n⚠️ No users have bypassed warnings.\n\n"

        try:
            # Telegram has a message length limit (4096 characters)
            if len(msg) > 4000:
                for i in range(0, len(msg), 4000):
                    chunk = msg[i:i+4000]
                    await update.message.reply_text(
                        chunk,
                        parse_mode='HTML'
                    )
            else:
                await update.message.reply_text(
                    msg,
                    parse_mode='HTML'
                )
            logger.info("Displayed comprehensive bot overview.")
        except Exception as e:
            logger.error(f"Error sending /list information: {e}")
            message = "⚠️ An error occurred while sending the list information."
            await update.message.reply_text(
                message,
                parse_mode='HTML'
            )

async def get_id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /get_id command to retrieve chat or user IDs.
    """
    chat = update.effective_chat
    user_id = update.effective_user.id
    logger.debug(f"/get_id command called in chat {chat.id} by user {user_id}")
    try:
        if chat.type in ["group", "supergroup"]:
            message = f"🔢 <b>Group ID:</b> <code>{chat.id}</code>"
            await update.message.reply_text(
                message,
                parse_mode='HTML'
            )
            logger.info(f"Retrieved Group ID {chat.id} in group chat by user {user_id}")
        else:
            message = f"🔢 <b>Your User ID:</b> <code>{user_id}</code>"
            await update.message.reply_text(
                message,
                parse_mode='HTML'
            )
            logger.info(f"Retrieved User ID {user_id} in private chat.")
    except Exception as e:
        logger.error(f"Error handling /get_id command: {e}")
        message = "⚠️ An error occurred while processing the command."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )

async def test_arabic_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /test_arabic command to test Arabic detection.
    Usage: /test_arabic <text>
    """
    text = ' '.join(context.args)
    logger.debug(f"/test_arabic command called with text: {text}")
    if not text:
        message = "⚠️ Usage: `/test_arabic <text>`"
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )
        return
    try:
        # Placeholder for check_arabic function
        # Implement your Arabic detection logic here
        # Example implementation using regex
        import re
        arabic_pattern = re.compile('[\u0600-\u06FF]')
        result = bool(arabic_pattern.search(text))
        confirmation_message = f"✅ Contains Arabic: <b>{result}</b>"
        await update.message.reply_text(
            confirmation_message,
            parse_mode='HTML'
        )
        logger.debug(f"Arabic detection for '{text}': {result}")
    except Exception as e:
        logger.error(f"Error processing /test_arabic command: {e}")
        message = "⚠️ An error occurred while processing the command."
        await update.message.reply_text(
            message,
            parse_mode='HTML'
        )

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

    # Initialize delete_enabled state
    initial_delete_state = get_setting('delete_enabled')
    if initial_delete_state == 'true':
        try:
            application.add_handler(be_sad_handler, group=10)  # Adjust group as necessary
            application.add_handler(be_happy_handler, group=10)  # Adjust group as necessary
            logger.info("Delete functionality enabled on startup based on stored settings.")
        except Exception as e:
            logger.error(f"Failed to enable delete functionality on startup: {e}")
    else:
        logger.info("Delete functionality is disabled on startup based on stored settings.")

    # Register existing command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("set", set_warnings_cmd))
    application.add_handler(CommandHandler("tara_G", tara_g_cmd))
    application.add_handler(CommandHandler("rmove_G", remove_global_tara_cmd))
    application.add_handler(CommandHandler("tara", tara_cmd))
    application.add_handler(CommandHandler("rmove_t", rmove_tara_cmd))
    application.add_handler(CommandHandler("group_add", group_add_cmd))
    application.add_handler(CommandHandler("group_remove", rmove_group_cmd))  # Assuming /group_remove corresponds to /rmove_group
    application.add_handler(CommandHandler("tara_link", tara_link_cmd))
    application.add_handler(CommandHandler("unlink_tara", unlink_tara_cmd))
    application.add_handler(CommandHandler("bypass", bypass_cmd))
    application.add_handler(CommandHandler("unbypass", unbypass_cmd))
    application.add_handler(CommandHandler("show", show_groups_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("info", info_cmd))
    application.add_handler(CommandHandler("list", list_cmd))
    application.add_handler(CommandHandler("get_id", get_id_cmd))
    application.add_handler(CommandHandler("test_arabic", test_arabic_cmd))
    
    # Register the new /be_sad and /be_happy commands from delete.py
    # These handlers are already added above if delete_enabled is true
    
    # Handle private messages for setting group name
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        handle_private_message_for_group_name
    ))

    # Handle group messages for issuing warnings
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP),
        handle_warnings
    ))

    # Register error handler
    application.add_error_handler(error_handler)

    logger.info("🚀 Bot starting...")
    try:
        application.run_polling()
    except Exception as e:
        logger.critical(f"Bot encountered a critical error and is shutting down: {e}")
        sys.exit(f"Bot encountered a critical error and is shutting down: {e}")

if __name__ == '__main__':
    main()
