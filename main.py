# main.py

import os
import sqlite3
import logging
import html
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

# Import warning_handler functions
from warning_handler import handle_warnings, check_arabic

# Define the path to the SQLite database
DATABASE = 'warnings.db'

# Replace with your actual SUPER_ADMIN_ID (integer)
SUPER_ADMIN_ID = 6177929931  # <-- Set this to your Telegram user ID

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO  # Set to DEBUG for more verbose output
)
logger = logging.getLogger(__name__)

# Dictionary to keep track of pending group names
pending_group_names = {}

def init_db():
    """
    Initialize the SQLite database and create necessary tables if they don't exist.
    Also, add the 'arabic_deletion_enabled' column to the 'groups' table.
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
                arabic_deletion_enabled INTEGER NOT NULL DEFAULT 0
            )
        ''')

        # Create tara_links table
        c.execute('''
            CREATE TABLE IF NOT EXISTS tara_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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

        # Create arabic_deletion_groups table to track groups with Arabic deletion activated
        # This is optional since we have 'arabic_deletion_enabled' in groups table
        # If you prefer a separate table, uncomment the following lines
        # c.execute('''
        #     CREATE TABLE IF NOT EXISTS arabic_deletion_groups (
        #         group_id INTEGER PRIMARY KEY,
        #         FOREIGN KEY(group_id) REFERENCES groups(group_id)
        #     )
        # ''')

        conn.commit()
        conn.close()
        logger.info("Database initialized successfully.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            logger.info("'arabic_deletion_enabled' column already exists in 'groups' table.")
        else:
            logger.error(f"Failed to initialize the database: {e}")
            raise
    except Exception as e:
        logger.error(f"Failed to initialize the database: {e}")
        raise

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
        # Check if the link already exists to prevent duplicates
        c.execute('SELECT 1 FROM tara_links WHERE tara_user_id = ? AND group_id = ?', (tara_id, g_id))
        if c.fetchone():
            logger.warning(f"TARA {tara_id} is already linked to group {g_id}.")
            return
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
            logger.warning(f"TARA {tara_id} was not linked to group {g_id}")
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

async def handle_private_message_for_group_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle private messages sent by SUPER_ADMIN to set group names.
    """
    if update.effective_chat.type != ChatType.PRIVATE:
        return
    message = update.message
    user = message.from_user
    logger.debug(f"Received private message from user {user.id}: {message.text}")
    if user.id == SUPER_ADMIN_ID and user.id in pending_group_names:
        g_id = pending_group_names.pop(user.id)
        group_name = message.text.strip()
        if group_name:
            try:
                set_group_name(g_id, group_name)
                await message.reply_text(
                    f"✅ Group name for `<code>{g_id}</code>` set to: <b>{html.escape(group_name)}</b>",
                    parse_mode='HTML'
                )
                logger.info(f"Group name for {g_id} set to {group_name} by SUPER_ADMIN {user.id}")
            except Exception as e:
                await message.reply_text(
                    "⚠️ Failed to set group name. Please try `/group_add` again.",
                    parse_mode='MarkdownV2'
                )
                logger.error(f"Error setting group name for {g_id} by SUPER_ADMIN {user.id}: {e}")
        else:
            await message.reply_text(
                "⚠️ Group name cannot be empty. Please try `/group_add` again.",
                parse_mode='MarkdownV2'
            )
            logger.warning(f"Empty group name received from SUPER_ADMIN {user.id} for group {g_id}")
    else:
        await message.reply_text(
            "⚠️ No pending group to set name for.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Received group name from user {user.id} with no pending group.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /start command.
    """
    try:
        await update.message.reply_text(
            "✅ Bot is running and ready.",
            parse_mode='MarkdownV2'
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
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /set by user {user.id}")
        return
    args = context.args
    if len(args) != 2:
        await update.message.reply_text(
            "⚠️ Usage: `/set <user_id> <number>`",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /set by SUPER_ADMIN {user.id}")
        return
    try:
        target_user_id = int(args[0])
        new_warnings = int(args[1])
    except ValueError:
        await update.message.reply_text(
            "⚠️ Both `user_id` and `number` must be integers.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer arguments provided to /set by SUPER_ADMIN {user.id}")
        return
    if new_warnings < 0:
        await update.message.reply_text(
            "⚠️ Number of warnings cannot be negative.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Negative warnings provided to /set by SUPER_ADMIN {user.id}")
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
        logger.info(f"Set {new_warnings} warnings for user {target_user_id} by SUPER_ADMIN {user.id}")
    except Exception as e:
        await update.message.reply_text(
            "⚠️ Failed to set warnings. Please try again later.",
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error setting warnings for user {target_user_id} by SUPER_ADMIN {user.id}: {e}")
        return

    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"🔧 Your number of warnings has been set to `<code>{new_warnings}</code>` by the administrator.",
            parse_mode='HTML'
        )
        logger.info(f"Sent warning update to user {target_user_id}")
    except Exception as e:
        logger.error(f"Error sending warning update to user {target_user_id}: {e}")

    await update.message.reply_text(
        f"✅ Set `<code>{new_warnings}</code>` warnings for user ID `<code>{target_user_id}</code>`.",
        parse_mode='HTML'
    )
    logger.debug(f"Responded to /set command by SUPER_ADMIN {user.id}")

async def tara_g_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /tara_G command to add a Global TARA admin.
    Usage: /tara_G <admin_id>
    """
    user = update.effective_user
    logger.debug(f"/tara_G command called by user {user.id} with args: {context.args}")
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /tara_G by user {user.id}")
        return
    if len(context.args) != 1:
        await update.message.reply_text(
            "⚠️ Usage: `/tara_G <admin_id>`",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /tara_G by SUPER_ADMIN {user.id}")
        return
    try:
        new_admin_id = int(context.args[0])
        logger.debug(f"Parsed new_admin_id: {new_admin_id}")
    except ValueError:
        await update.message.reply_text(
            "⚠️ `admin_id` must be an integer.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer admin_id provided to /tara_G by SUPER_ADMIN {user.id}")
        return
    try:
        add_global_tara(new_admin_id)
        logger.debug(f"Added global TARA {new_admin_id} to database.")
    except Exception as e:
        await update.message.reply_text(
            "⚠️ Failed to add global TARA. Please try again later.",
            parse_mode='MarkdownV2'
        )
        logger.error(f"Failed to add global TARA admin {new_admin_id} by SUPER_ADMIN {user.id}: {e}")
        return

    try:
        await update.message.reply_text(
            f"✅ Added global TARA admin `<code>{new_admin_id}</code>`.",
            parse_mode='HTML'
        )
        logger.info(f"Added global TARA admin {new_admin_id} by SUPER_ADMIN {user.id}")
    except Exception as e:
        logger.error(f"Error sending reply for /tara_G command: {e}")

async def remove_global_tara_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /rmove_G command to remove a Global TARA admin.
    Usage: /rmove_G <tara_id>
    """
    user = update.effective_user
    logger.debug(f"/rmove_G command called by user {user.id} with args: {context.args}")
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /rmove_G by user {user.id}")
        return
    if len(context.args) != 1:
        await update.message.reply_text(
            "⚠️ Usage: `/rmove_G <tara_id>`",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /rmove_G by SUPER_ADMIN {user.id}")
        return
    try:
        tara_id = int(context.args[0])
        logger.debug(f"Parsed tara_id: {tara_id}")
    except ValueError:
        await update.message.reply_text(
            "⚠️ `tara_id` must be an integer.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer tara_id provided to /rmove_G by SUPER_ADMIN {user.id}")
        return

    try:
        if remove_global_tara(tara_id):
            await update.message.reply_text(
                f"✅ Removed global TARA `<code>{tara_id}</code>`.",
                parse_mode='HTML'
            )
            logger.info(f"Removed global TARA {tara_id} by SUPER_ADMIN {user.id}")
        else:
            await update.message.reply_text(
                f"⚠️ Global TARA `<code>{tara_id}</code>` not found.",
                parse_mode='HTML'
            )
            logger.warning(f"Attempted to remove non-existent global TARA {tara_id} by SUPER_ADMIN {user.id}")
    except Exception as e:
        await update.message.reply_text(
            "⚠️ Failed to remove global TARA. Please try again later.",
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error removing global TARA {tara_id} by SUPER_ADMIN {user.id}: {e}")

async def tara_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /tara command to add a normal TARA.
    Usage: /tara <tara_id>
    """
    user = update.effective_user
    logger.debug(f"/tara command called by user {user.id} with args: {context.args}")
    
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /tara by user {user.id}")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text(
            "⚠️ Usage: `/tara <tara_id>`",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /tara by SUPER_ADMIN {user.id}")
        return
    
    try:
        tara_id = int(context.args[0])
        logger.debug(f"Parsed tara_id: {tara_id}")
    except ValueError:
        await update.message.reply_text(
            "⚠️ `tara_id` must be an integer.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer tara_id provided to /tara by SUPER_ADMIN {user.id}")
        return
    
    try:
        add_normal_tara(tara_id)
        logger.debug(f"Added normal TARA {tara_id} to database.")
    except Exception as e:
        await update.message.reply_text(
            "⚠️ Failed to add TARA. Please try again later.",
            parse_mode='MarkdownV2'
        )
        logger.error(f"Failed to add normal TARA {tara_id} by SUPER_ADMIN {user.id}: {e}")
        return
    
    try:
        await update.message.reply_text(
            f"✅ Added normal TARA `<code>{tara_id}</code>`.",
            parse_mode='HTML'
        )
        logger.info(f"Added normal TARA {tara_id} by SUPER_ADMIN {user.id}")
    except Exception as e:
        logger.error(f"Error sending reply for /tara command: {e}")

async def group_add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /group_add command to register a group.
    Usage: /group_add <group_id>
    """
    user = update.effective_user
    logger.debug(f"/group_add command called by user {user.id} with args: {context.args}")
    
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /group_add by user {user.id}")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text(
            "⚠️ Usage: `/group_add <group_id>`",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /group_add by SUPER_ADMIN {user.id}")
        return
    
    try:
        group_id = int(context.args[0])
        logger.debug(f"Parsed group_id: {group_id}")
    except ValueError:
        await update.message.reply_text(
            "⚠️ `group_id` must be an integer.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer group_id provided to /group_add by SUPER_ADMIN {user.id}")
        return
    
    if group_exists(group_id):
        await update.message.reply_text(
            "⚠️ Group already added.",
            parse_mode='MarkdownV2'
        )
        logger.debug(f"Group {group_id} is already registered.")
        return
    
    try:
        add_group(group_id)
        logger.debug(f"Added group {group_id} to database.")
    except Exception as e:
        await update.message.reply_text(
            "⚠️ Failed to add group. Please try again later.",
            parse_mode='MarkdownV2'
        )
        logger.error(f"Failed to add group {group_id} by SUPER_ADMIN {user.id}: {e}")
        return
    
    pending_group_names[user.id] = group_id
    logger.info(f"Group {group_id} added, awaiting name from SUPER_ADMIN {user.id} in private chat.")
    
    await update.message.reply_text(
        f"✅ Group `<code>{group_id}</code>` added.\nPlease send the group name in a private message to the bot.",
        parse_mode='HTML'
    )

async def rmove_group_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /rmove_group command to remove a registered group.
    Usage: /rmove_group <group_id>
    """
    user = update.effective_user
    logger.debug(f"/rmove_group command called by user {user.id} with args: {context.args}")
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /rmove_group by user {user.id}")
        return
    if len(context.args) != 1:
        await update.message.reply_text(
            "⚠️ Usage: `/rmove_group <group_id>`",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /rmove_group by SUPER_ADMIN {user.id}")
        return
    try:
        group_id = int(context.args[0])
        logger.debug(f"Parsed group_id: {group_id}")
    except ValueError:
        await update.message.reply_text(
            "⚠️ `group_id` must be an integer.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer group_id provided to /rmove_group by SUPER_ADMIN {user.id}")
        return

    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('DELETE FROM groups WHERE group_id = ?', (group_id,))
        changes = c.rowcount
        # Also remove any tara_links associated with this group
        c.execute('DELETE FROM tara_links WHERE group_id = ?', (group_id,))
        conn.commit()
        conn.close()
        if changes > 0:
            await update.message.reply_text(
                f"✅ Removed group `<code>{group_id}</code>` from registration.",
                parse_mode='HTML'
            )
            logger.info(f"Removed group {group_id} by SUPER_ADMIN {user.id}")
        else:
            await update.message.reply_text(
                f"⚠️ Group `<code>{group_id}</code>` not found.",
                parse_mode='HTML'
            )
            logger.warning(f"Attempted to remove non-existent group {group_id} by SUPER_ADMIN {user.id}")
    except Exception as e:
        await update.message.reply_text(
            "⚠️ Failed to remove group. Please try again later.",
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error removing group {group_id} by SUPER_ADMIN {user.id}: {e}")

async def unlink_tara_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /unlink_tara command to unlink a TARA from a group.
    Usage: /unlink_tara <tara_id> <group_id>
    """
    user = update.effective_user
    logger.debug(f"/unlink_tara command called by user {user.id} with args: {context.args}")
    
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /unlink_tara by user {user.id}")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text(
            "⚠️ Usage: `/unlink_tara <tara_id> <group_id>`",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /unlink_tara by SUPER_ADMIN {user.id}")
        return
    
    try:
        tara_id = int(context.args[0])
        group_id = int(context.args[1])
        logger.debug(f"Parsed tara_id: {tara_id}, group_id: {group_id}")
    except ValueError:
        await update.message.reply_text(
            "⚠️ Both `tara_id` and `group_id` must be integers.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer arguments provided to /unlink_tara by SUPER_ADMIN {user.id}")
        return
    
    if not group_exists(group_id):
        await update.message.reply_text(
            "⚠️ Group not found.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Attempted to unlink TARA {tara_id} from non-existent group {group_id} by SUPER_ADMIN {user.id}")
        return
    
    try:
        if unlink_tara_from_group(tara_id, group_id):
            await update.message.reply_text(
                f"✅ Unlinked TARA `<code>{tara_id}</code>` from group `<code>{group_id}</code>`.",
                parse_mode='HTML'
            )
            logger.info(f"Unlinked TARA {tara_id} from group {group_id} by SUPER_ADMIN {user.id}")
        else:
            await update.message.reply_text(
                f"⚠️ TARA `<code>{tara_id}</code>` was not linked to group `<code>{group_id}</code>`.",
                parse_mode='HTML'
            )
            logger.warning(f"Attempted to unlink non-linked TARA {tara_id} from group {group_id} by SUPER_ADMIN {user.id}")
    except Exception as e:
        await update.message.reply_text(
            "⚠️ Failed to unlink TARA from group. Please try again later.",
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error unlinking TARA {tara_id} from group {group_id} by SUPER_ADMIN {user.id}: {e}")

async def tara_link_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /tara_link command to link a TARA to a group.
    Usage: /tara_link <tara_id> <group_id>
    """
    user = update.effective_user
    logger.debug(f"/tara_link command called by user {user.id} with args: {context.args}")
    
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /tara_link by user {user.id}")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text(
            "⚠️ Usage: `/tara_link <tara_id> <group_id>`",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /tara_link by SUPER_ADMIN {user.id}")
        return
    
    try:
        tara_id = int(context.args[0])
        g_id = int(context.args[1])
        logger.debug(f"Parsed tara_id: {tara_id}, group_id: {g_id}")
    except ValueError:
        await update.message.reply_text(
            "⚠️ Both `tara_id` and `group_id` must be integers.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer arguments provided to /tara_link by SUPER_ADMIN {user.id}")
        return
    
    if not group_exists(g_id):
        await update.message.reply_text(
            "⚠️ Group not added.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Attempted to link TARA {tara_id} to non-registered group {g_id} by SUPER_ADMIN {user.id}")
        return
    
    try:
        link_tara_to_group(tara_id, g_id)
        logger.debug(f"Linked TARA {tara_id} to group {g_id}.")
    except Exception as e:
        await update.message.reply_text(
            "⚠️ Failed to link TARA to group. Please try again later.",
            parse_mode='MarkdownV2'
        )
        logger.error(f"Failed to link TARA {tara_id} to group {g_id} by SUPER_ADMIN {user.id}: {e}")
        return
    
    try:
        await update.message.reply_text(
            f"✅ Linked TARA `<code>{tara_id}</code>` to group `<code>{g_id}</code>`.",
            parse_mode='HTML'
        )
        logger.info(f"Linked TARA {tara_id} to group {g_id} by SUPER_ADMIN {user.id}")
    except Exception as e:
        logger.error(f"Error sending reply for /tara_link command: {e}")

async def bypass_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /bypass command to add a user to bypass warnings.
    Usage: /bypass <user_id>
    """
    user = update.effective_user
    logger.debug(f"/bypass command called by user {user.id} with args: {context.args}")
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /bypass by user {user.id}")
        return
    if len(context.args) != 1:
        await update.message.reply_text(
            "⚠️ Usage: `/bypass <user_id>`",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /bypass by SUPER_ADMIN {user.id}")
        return
    try:
        target_user_id = int(context.args[0])
        logger.debug(f"Parsed target_user_id: {target_user_id}")
    except ValueError:
        await update.message.reply_text(
            "⚠️ `user_id` must be an integer.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer user_id provided to /bypass by SUPER_ADMIN {user.id}")
        return
    try:
        add_bypass_user(target_user_id)
        logger.debug(f"Added bypass user {target_user_id} to database.")
    except Exception as e:
        await update.message.reply_text(
            "⚠️ Failed to add bypass user. Please try again later.",
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error adding bypass user {target_user_id} by SUPER_ADMIN {user.id}: {e}")
        return
    try:
        await update.message.reply_text(
            f"✅ User `<code>{target_user_id}</code>` has been added to bypass warnings.",
            parse_mode='HTML'
        )
        logger.info(f"Added user {target_user_id} to bypass list by SUPER_ADMIN {user.id}")
    except Exception as e:
        logger.error(f"Error sending reply for /bypass command: {e}")

async def unbypass_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /unbypass command to remove a user from bypass warnings.
    Usage: /unbypass <user_id>
    """
    user = update.effective_user
    logger.debug(f"/unbypass command called by user {user.id} with args: {context.args}")
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /unbypass by user {user.id}")
        return
    if len(context.args) != 1:
        await update.message.reply_text(
            "⚠️ Usage: `/unbypass <user_id>`",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /unbypass by SUPER_ADMIN {user.id}")
        return
    try:
        target_user_id = int(context.args[0])
        logger.debug(f"Parsed target_user_id: {target_user_id}")
    except ValueError:
        await update.message.reply_text(
            "⚠️ `user_id` must be an integer.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer user_id provided to /unbypass by SUPER_ADMIN {user.id}")
        return
    try:
        if remove_bypass_user(target_user_id):
            await update.message.reply_text(
                f"✅ User `<code>{target_user_id}</code>` has been removed from bypass warnings.",
                parse_mode='HTML'
            )
            logger.info(f"Removed user {target_user_id} from bypass list by SUPER_ADMIN {user.id}")
        else:
            await update.message.reply_text(
                f"⚠️ User `<code>{target_user_id}</code>` was not in the bypass list.",
                parse_mode='HTML'
            )
            logger.warning(f"Attempted to remove non-existent bypass user {target_user_id} by SUPER_ADMIN {user.id}")
    except Exception as e:
        await update.message.reply_text(
            "⚠️ Failed to remove bypass user. Please try again later.",
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error removing bypass user {target_user_id} by SUPER_ADMIN {user.id}: {e}")

async def show_groups_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /show command to display all groups and linked TARAs.
    """
    user = update.effective_user
    logger.debug(f"/show command called by user {user.id}")
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /show by user {user.id}")
        return
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT group_id, group_name, arabic_deletion_enabled FROM groups')
        groups_data = c.fetchall()
        conn.close()

        if not groups_data:
            await update.message.reply_text(
                "⚠️ No groups added.",
                parse_mode='MarkdownV2'
            )
            logger.debug("No groups found in the database.")
            return

        msg = "*Groups Information:*\n\n"
        for g_id, g_name, arabic_deletion in groups_data:
            g_name_display = g_name if g_name else "No Name Set"
            g_name_esc = escape_markdown(g_name_display, version=2)
            arabic_status = "✅ Enabled" if arabic_deletion else "❌ Disabled"
            msg += f"• *Group ID:* `{g_id}`\n"
            msg += f"  *Name:* {g_name_esc}\n"
            msg += f"  *Arabic Deletion:* {arabic_status}\n"
            try:
                conn = sqlite3.connect(DATABASE)
                c = conn.cursor()
                c.execute('SELECT tara_user_id FROM tara_links WHERE group_id = ?', (g_id,))
                taras = c.fetchall()
                conn.close()
                if taras:
                    msg += "  *TARAs linked:*\n"
                    for t_id in taras:
                        msg += f"    • `{t_id[0]}`\n"
                else:
                    msg += "  No TARAs linked.\n"
            except Exception as e:
                msg += "  ⚠️ Error retrieving TARAs.\n"
                logger.error(f"Error retrieving TARAs for group {g_id}: {e}")
            msg += "\n"

        try:
            # Telegram has a message length limit (4096 characters)
            if len(msg) > 4000:
                for i in range(0, len(msg), 4000):
                    await update.message.reply_text(
                        msg[i:i+4000],
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
            await update.message.reply_text(
                "⚠️ An error occurred while sending the groups information.",
                parse_mode='MarkdownV2'
            )
    except Exception as e:
        logger.error(f"Error processing /show command: {e}")
        await update.message.reply_text(
            "⚠️ Failed to retrieve groups information. Please try again later.",
            parse_mode='MarkdownV2'
        )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /help command to display available commands.
    """
    user = update.effective_user
    logger.debug(f"/help command called by user {user.id}, SUPER_ADMIN_ID={SUPER_ADMIN_ID}")
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /help by user {user.id}")
        return
    help_text = """*Available Commands (SUPER_ADMIN only):*
• `/start` - Check if bot is running
• `/set <user_id> <number>` - Set warnings for a user
• `/tara_G <admin_id>` - Add a Global TARA admin
• `/rmove_G <tara_id>` - Remove a Global TARA admin
• `/tara <tara_id>` - Add a Normal TARA
• `/rmove_t <tara_id>` - Remove a Normal TARA
• `/unlink_tara <tara_id> <group_id>` - Unlink a TARA from a group
• `/group_add <group_id>` - Register a group (use the exact chat_id of the group)
• `/rmove_group <group_id>` - Remove a registered group
• `/tara_link <tara_id> <group_id>` - Link a TARA (Global or Normal) to a group
• `/unlink_tara <tara_id> <group_id>` - Unlink a TARA from a group
• `/bypass <user_id>` - Add a user to bypass warnings
• `/unbypass <user_id>` - Remove a user from bypass warnings
• `/show` - Show all groups and linked TARAs
• `/info` - Show warnings info
• `/get_id` - Get your or the group ID
• `/be_sad <group_id>` - Activate Arabic text deletion in a group
• `/help` - Show this help
• `/test_arabic <text>` - Test Arabic detection
"""
    try:
        # Escape special characters for MarkdownV2
        help_text_esc = escape_markdown(help_text, version=2)
        await update.message.reply_text(
            help_text_esc,
            parse_mode='MarkdownV2'
        )
        logger.info("Displayed help information to SUPER_ADMIN.")
    except Exception as e:
        logger.error(f"Error sending help information: {e}")
        await update.message.reply_text(
            "⚠️ An error occurred while sending the help information.",
            parse_mode='MarkdownV2'
        )

async def info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /info command to show warnings information.
    """
    user = update.effective_user
    user_id = user.id
    logger.debug(f"/info command called by user {user_id}")

    try:
        if user_id == SUPER_ADMIN_ID or is_global_tara(user_id):
            # Super Admin or Global TARA can see all warnings
            query = '''
                SELECT g.group_id, g.group_name, u.user_id, u.first_name, u.last_name, u.username, COUNT(w.id)
                FROM warnings_history w
                JOIN users u ON w.user_id = u.user_id
                JOIN groups g ON w.group_id = g.group_id
                GROUP BY g.group_id, u.user_id
                ORDER BY g.group_id, COUNT(w.id) DESC
            '''
            params = ()
        elif is_normal_tara(user_id):
            # Normal TARA can see warnings in linked groups
            linked_groups = get_linked_groups_for_tara(user_id)
            if not linked_groups:
                await update.message.reply_text(
                    "⚠️ No linked groups or permission.",
                    parse_mode='MarkdownV2'
                )
                logger.debug(f"TARA {user_id} has no linked groups.")
                return
            placeholders = ','.join('?' for _ in linked_groups)
            query = f'''
                SELECT g.group_id, g.group_name, u.user_id, u.first_name, u.last_name, u.username, COUNT(w.id)
                FROM warnings_history w
                JOIN users u ON w.user_id = u.user_id
                JOIN groups g ON w.group_id = g.group_id
                WHERE w.group_id IN ({placeholders})
                GROUP BY g.group_id, u.user_id
                ORDER BY g.group_id, COUNT(w.id) DESC
            '''
            params = linked_groups
        else:
            await update.message.reply_text(
                "⚠️ You don't have permission to view warnings.",
                parse_mode='MarkdownV2'
            )
            logger.warning(f"User {user_id} attempted to use /info without permissions.")
            return

        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()

        if not rows:
            await update.message.reply_text(
                "⚠️ No warnings found.",
                parse_mode='MarkdownV2'
            )
            logger.debug("No warnings found to display.")
            return

        from collections import defaultdict
        group_data = defaultdict(list)
        for g_id, g_name, u_id, f_name, l_name, uname, w_count in rows:
            group_data[g_id].append((g_name, u_id, f_name, l_name, uname, w_count))

        msg = "*Warnings Information:*\n\n"
        for g_id, info_list in group_data.items():
            group_name = info_list[0][0] if info_list[0][0] else "No Name"
            group_name_esc = escape_markdown(group_name, version=2)
            msg += f"*Group:* {group_name_esc}\n*Group ID:* `{g_id}`\n"
            for (_, u_id, f_name, l_name, uname, w_count) in info_list:
                full_name = (f"{f_name or ''} {l_name or ''}".strip() or "N/A")
                full_name_esc = escape_markdown(full_name, version=2)
                username_esc = f"@{escape_markdown(uname, version=2)}" if uname else "NoUsername"
                msg += (
                    f"• *User ID:* `{u_id}`\n"
                    f"  *Full Name:* {full_name_esc}\n"
                    f"  *Username:* {username_esc}\n"
                    f"  *Warnings in this group:* `{w_count}`\n\n"
                )

        try:
            # Telegram has a message length limit (4096 characters)
            if len(msg) > 4000:
                for i in range(0, len(msg), 4000):
                    await update.message.reply_text(
                        msg[i:i+4000],
                        parse_mode='MarkdownV2'
                    )
            else:
                await update.message.reply_text(
                    msg,
                    parse_mode='MarkdownV2'
                )
            logger.info("Displayed warnings information.")
        except Exception as e:
            logger.error(f"Error sending warnings information: {e}")
            await update.message.reply_text(
                "⚠️ An error occurred while sending the warnings information.",
                parse_mode='MarkdownV2'
            )
    except Exception as e:
        logger.error(f"Error processing /info command: {e}")
        await update.message.reply_text(
            "⚠️ Failed to retrieve warnings information. Please try again later.",
            parse_mode='MarkdownV2'
        )

async def get_id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /get_id command to retrieve chat or user IDs.
    Restricted to SUPER_ADMIN only.
    """
    user = update.effective_user
    logger.debug(f"/get_id command called by user {user.id}")
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /get_id by user {user.id}")
        return
    chat = update.effective_chat
    user_id = user.id
    try:
        if chat.type in ["group", "supergroup"]:
            await update.message.reply_text(
                f"🔢 *Group ID:* `{chat.id}`",
                parse_mode='MarkdownV2'
            )
            logger.info(f"Retrieved Group ID {chat.id} in group chat by SUPER_ADMIN {user.id}")
        else:
            await update.message.reply_text(
                f"🔢 *Your User ID:* `{user_id}`",
                parse_mode='MarkdownV2'
            )
            logger.info(f"Retrieved User ID {user_id} in private chat by SUPER_ADMIN")
    except Exception as e:
        logger.error(f"Error handling /get_id command: {e}")
        await update.message.reply_text(
            "⚠️ An error occurred while processing the command.",
            parse_mode='MarkdownV2'
        )

async def be_sad_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /be_sad command to activate Arabic text deletion in a group.
    Usage: /be_sad <group_id>
    """
    user = update.effective_user
    logger.debug(f"/be_sad command called by user {user.id} with args: {context.args}")
    
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /be_sad by user {user.id}")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text(
            "⚠️ Usage: `/be_sad <group_id>`",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /be_sad by SUPER_ADMIN {user.id}")
        return
    
    try:
        group_id = int(context.args[0])
        logger.debug(f"Parsed group_id: {group_id}")
    except ValueError:
        await update.message.reply_text(
            "⚠️ `group_id` must be an integer.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer group_id provided to /be_sad by SUPER_ADMIN {user.id}")
        return
    
    if not group_exists(group_id):
        await update.message.reply_text(
            "⚠️ Group not found.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Attempted to activate Arabic deletion for non-existent group {group_id} by SUPER_ADMIN {user.id}")
        return
    
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('UPDATE groups SET arabic_deletion_enabled = 1 WHERE group_id = ?', (group_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text(
            f"✅ Arabic text deletion activated for group `<code>{group_id}</code>`.",
            parse_mode='HTML'
        )
        logger.info(f"Activated Arabic text deletion for group {group_id} by SUPER_ADMIN {user.id}")
    except Exception as e:
        await update.message.reply_text(
            "⚠️ Failed to activate Arabic text deletion. Please try again later.",
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error activating Arabic text deletion for group {group_id} by SUPER_ADMIN {user.id}: {e}")

async def be_sad_toggle_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /be_sad_off command to deactivate Arabic text deletion in a group.
    Usage: /be_sad_off <group_id>
    """
    user = update.effective_user
    logger.debug(f"/be_sad_off command called by user {user.id} with args: {context.args}")
    
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /be_sad_off by user {user.id}")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text(
            "⚠️ Usage: `/be_sad_off <group_id>`",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /be_sad_off by SUPER_ADMIN {user.id}")
        return
    
    try:
        group_id = int(context.args[0])
        logger.debug(f"Parsed group_id: {group_id}")
    except ValueError:
        await update.message.reply_text(
            "⚠️ `group_id` must be an integer.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer group_id provided to /be_sad_off by SUPER_ADMIN {user.id}")
        return
    
    if not group_exists(group_id):
        await update.message.reply_text(
            "⚠️ Group not found.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Attempted to deactivate Arabic deletion for non-existent group {group_id} by SUPER_ADMIN {user.id}")
        return
    
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('UPDATE groups SET arabic_deletion_enabled = 0 WHERE group_id = ?', (group_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text(
            f"✅ Arabic text deletion deactivated for group `<code>{group_id}</code>`.",
            parse_mode='HTML'
        )
        logger.info(f"Deactivated Arabic text deletion for group {group_id} by SUPER_ADMIN {user.id}")
    except Exception as e:
        await update.message.reply_text(
            "⚠️ Failed to deactivate Arabic text deletion. Please try again later.",
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error deactivating Arabic text deletion for group {group_id} by SUPER_ADMIN {user.id}: {e}")

async def handle_warnings_with_arabic_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Enhanced handle_warnings function that also handles Arabic text deletion.
    """
    # First, handle warnings as usual
    await handle_warnings(update, context)
    
    # Now, handle Arabic text deletion
    chat = update.effective_chat
    message = update.message
    user = update.effective_user

    if chat.type not in ["group", "supergroup"]:
        return  # Only handle group messages

    group_id = chat.id

    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT arabic_deletion_enabled FROM groups WHERE group_id = ?', (group_id,))
        result = c.fetchone()
        conn.close()
        if result and result[0] == 1:
            # Arabic deletion is enabled for this group
            text = message.text or ""
            if await check_arabic(text):
                if not is_bypass_user(user.id):
                    try:
                        await message.delete()
                        logger.info(f"Deleted Arabic message from user {user.id} in group {group_id}")
                    except Exception as e:
                        logger.error(f"Failed to delete message from user {user.id} in group {group_id}: {e}")
    except Exception as e:
        logger.error(f"Error processing Arabic deletion for group {group_id}: {e}")

async def info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /info command to show warnings information.
    """
    user = update.effective_user
    user_id = user.id
    logger.debug(f"/info command called by user {user_id}")

    try:
        if user_id == SUPER_ADMIN_ID or is_global_tara(user_id):
            # Super Admin or Global TARA can see all warnings
            query = '''
                SELECT g.group_id, g.group_name, u.user_id, u.first_name, u.last_name, u.username, COUNT(w.id)
                FROM warnings_history w
                JOIN users u ON w.user_id = u.user_id
                JOIN groups g ON w.group_id = g.group_id
                GROUP BY g.group_id, u.user_id
                ORDER BY g.group_id, COUNT(w.id) DESC
            '''
            params = ()
        elif is_normal_tara(user_id):
            # Normal TARA can see warnings in linked groups
            linked_groups = get_linked_groups_for_tara(user_id)
            if not linked_groups:
                await update.message.reply_text(
                    "⚠️ No linked groups or permission.",
                    parse_mode='MarkdownV2'
                )
                logger.debug(f"TARA {user_id} has no linked groups.")
                return
            placeholders = ','.join('?' for _ in linked_groups)
            query = f'''
                SELECT g.group_id, g.group_name, u.user_id, u.first_name, u.last_name, u.username, COUNT(w.id)
                FROM warnings_history w
                JOIN users u ON w.user_id = u.user_id
                JOIN groups g ON w.group_id = g.group_id
                WHERE w.group_id IN ({placeholders})
                GROUP BY g.group_id, u.user_id
                ORDER BY g.group_id, COUNT(w.id) DESC
            '''
            params = linked_groups
        else:
            await update.message.reply_text(
                "⚠️ You don't have permission to view warnings.",
                parse_mode='MarkdownV2'
            )
            logger.warning(f"User {user_id} attempted to use /info without permissions.")
            return

        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()

        if not rows:
            await update.message.reply_text(
                "⚠️ No warnings found.",
                parse_mode='MarkdownV2'
            )
            logger.debug("No warnings found to display.")
            return

        from collections import defaultdict
        group_data = defaultdict(list)
        for g_id, g_name, u_id, f_name, l_name, uname, w_count in rows:
            group_data[g_id].append((g_name, u_id, f_name, l_name, uname, w_count))

        msg = "*Warnings Information:*\n\n"
        for g_id, info_list in group_data.items():
            group_name = info_list[0][0] if info_list[0][0] else "No Name"
            group_name_esc = escape_markdown(group_name, version=2)
            msg += f"*Group:* {group_name_esc}\n*Group ID:* `{g_id}`\n"
            for (_, u_id, f_name, l_name, uname, w_count) in info_list:
                full_name = (f"{f_name or ''} {l_name or ''}".strip() or "N/A")
                full_name_esc = escape_markdown(full_name, version=2)
                username_esc = f"@{escape_markdown(uname, version=2)}" if uname else "NoUsername"
                msg += (
                    f"• *User ID:* `{u_id}`\n"
                    f"  *Full Name:* {full_name_esc}\n"
                    f"  *Username:* {username_esc}\n"
                    f"  *Warnings in this group:* `{w_count}`\n\n"
                )

        try:
            # Telegram has a message length limit (4096 characters)
            if len(msg) > 4000:
                for i in range(0, len(msg), 4000):
                    await update.message.reply_text(
                        msg[i:i+4000],
                        parse_mode='MarkdownV2'
                    )
            else:
                await update.message.reply_text(
                    msg,
                    parse_mode='MarkdownV2'
                )
            logger.info("Displayed warnings information.")
        except Exception as e:
            logger.error(f"Error sending warnings information: {e}")
            await update.message.reply_text(
                "⚠️ An error occurred while sending the warnings information.",
                parse_mode='MarkdownV2'
            )
    except Exception as e:
        logger.error(f"Error processing /info command: {e}")
        await update.message.reply_text(
            "⚠️ Failed to retrieve warnings information. Please try again later.",
            parse_mode='MarkdownV2'
        )

async def be_sad_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /be_sad command to activate Arabic text deletion in a group.
    Usage: /be_sad <group_id>
    """
    user = update.effective_user
    logger.debug(f"/be_sad command called by user {user.id} with args: {context.args}")
    
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /be_sad by user {user.id}")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text(
            "⚠️ Usage: `/be_sad <group_id>`",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /be_sad by SUPER_ADMIN {user.id}")
        return
    
    try:
        group_id = int(context.args[0])
        logger.debug(f"Parsed group_id: {group_id}")
    except ValueError:
        await update.message.reply_text(
            "⚠️ `group_id` must be an integer.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer group_id provided to /be_sad by SUPER_ADMIN {user.id}")
        return
    
    if not group_exists(group_id):
        await update.message.reply_text(
            "⚠️ Group not found.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Attempted to activate Arabic deletion for non-existent group {group_id} by SUPER_ADMIN {user.id}")
        return
    
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('UPDATE groups SET arabic_deletion_enabled = 1 WHERE group_id = ?', (group_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text(
            f"✅ Arabic text deletion activated for group `<code>{group_id}</code>`.",
            parse_mode='HTML'
        )
        logger.info(f"Activated Arabic text deletion for group {group_id} by SUPER_ADMIN {user.id}")
    except Exception as e:
        await update.message.reply_text(
            "⚠️ Failed to activate Arabic text deletion. Please try again later.",
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error activating Arabic text deletion for group {group_id} by SUPER_ADMIN {user.id}: {e}")

async def be_sad_off_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /be_sad_off command to deactivate Arabic text deletion in a group.
    Usage: /be_sad_off <group_id>
    """
    user = update.effective_user
    logger.debug(f"/be_sad_off command called by user {user.id} with args: {context.args}")
    
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /be_sad_off by user {user.id}")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text(
            "⚠️ Usage: `/be_sad_off <group_id>`",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /be_sad_off by SUPER_ADMIN {user.id}")
        return
    
    try:
        group_id = int(context.args[0])
        logger.debug(f"Parsed group_id: {group_id}")
    except ValueError:
        await update.message.reply_text(
            "⚠️ `group_id` must be an integer.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer group_id provided to /be_sad_off by SUPER_ADMIN {user.id}")
        return
    
    if not group_exists(group_id):
        await update.message.reply_text(
            "⚠️ Group not found.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Attempted to deactivate Arabic deletion for non-existent group {group_id} by SUPER_ADMIN {user.id}")
        return
    
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('UPDATE groups SET arabic_deletion_enabled = 0 WHERE group_id = ?', (group_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text(
            f"✅ Arabic text deletion deactivated for group `<code>{group_id}</code>`.",
            parse_mode='HTML'
        )
        logger.info(f"Deactivated Arabic text deletion for group {group_id} by SUPER_ADMIN {user.id}")
    except Exception as e:
        await update.message.reply_text(
            "⚠️ Failed to deactivate Arabic text deletion. Please try again later.",
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error deactivating Arabic text deletion for group {group_id} by SUPER_ADMIN {user.id}: {e}")

async def handle_warnings_with_arabic_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Enhanced handle_warnings function that also handles Arabic text deletion.
    """
    # First, handle warnings as usual
    await handle_warnings(update, context)
    
    # Now, handle Arabic text deletion
    chat = update.effective_chat
    message = update.message
    user = update.effective_user

    if chat.type not in ["group", "supergroup"]:
        return  # Only handle group messages

    group_id = chat.id

    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT arabic_deletion_enabled FROM groups WHERE group_id = ?', (group_id,))
        result = c.fetchone()
        conn.close()
        if result and result[0] == 1:
            # Arabic deletion is enabled for this group
            text = message.text or ""
            if await check_arabic(text):
                if not is_bypass_user(user.id):
                    try:
                        await message.delete()
                        logger.info(f"Deleted Arabic message from user {user.id} in group {group_id}")
                    except Exception as e:
                        logger.error(f"Failed to delete message from user {user.id} in group {group_id}: {e}")
    except Exception as e:
        logger.error(f"Error processing Arabic deletion for group {group_id}: {e}")

async def info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /info command to show warnings information.
    """
    user = update.effective_user
    user_id = user.id
    logger.debug(f"/info command called by user {user_id}")

    try:
        if user_id == SUPER_ADMIN_ID or is_global_tara(user_id):
            # Super Admin or Global TARA can see all warnings
            query = '''
                SELECT g.group_id, g.group_name, u.user_id, u.first_name, u.last_name, u.username, COUNT(w.id)
                FROM warnings_history w
                JOIN users u ON w.user_id = u.user_id
                JOIN groups g ON w.group_id = g.group_id
                GROUP BY g.group_id, u.user_id
                ORDER BY g.group_id, COUNT(w.id) DESC
            '''
            params = ()
        elif is_normal_tara(user_id):
            # Normal TARA can see warnings in linked groups
            linked_groups = get_linked_groups_for_tara(user_id)
            if not linked_groups:
                await update.message.reply_text(
                    "⚠️ No linked groups or permission.",
                    parse_mode='MarkdownV2'
                )
                logger.debug(f"TARA {user_id} has no linked groups.")
                return
            placeholders = ','.join('?' for _ in linked_groups)
            query = f'''
                SELECT g.group_id, g.group_name, u.user_id, u.first_name, u.last_name, u.username, COUNT(w.id)
                FROM warnings_history w
                JOIN users u ON w.user_id = u.user_id
                JOIN groups g ON w.group_id = g.group_id
                WHERE w.group_id IN ({placeholders})
                GROUP BY g.group_id, u.user_id
                ORDER BY g.group_id, COUNT(w.id) DESC
            '''
            params = linked_groups
        else:
            await update.message.reply_text(
                "⚠️ You don't have permission to view warnings.",
                parse_mode='MarkdownV2'
            )
            logger.warning(f"User {user_id} attempted to use /info without permissions.")
            return

        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()

        if not rows:
            await update.message.reply_text(
                "⚠️ No warnings found.",
                parse_mode='MarkdownV2'
            )
            logger.debug("No warnings found to display.")
            return

        from collections import defaultdict
        group_data = defaultdict(list)
        for g_id, g_name, u_id, f_name, l_name, uname, w_count in rows:
            group_data[g_id].append((g_name, u_id, f_name, l_name, uname, w_count))

        msg = "*Warnings Information:*\n\n"
        for g_id, info_list in group_data.items():
            group_name = info_list[0][0] if info_list[0][0] else "No Name"
            group_name_esc = escape_markdown(group_name, version=2)
            msg += f"*Group:* {group_name_esc}\n*Group ID:* `{g_id}`\n"
            for (_, u_id, f_name, l_name, uname, w_count) in info_list:
                full_name = (f"{f_name or ''} {l_name or ''}".strip() or "N/A")
                full_name_esc = escape_markdown(full_name, version=2)
                username_esc = f"@{escape_markdown(uname, version=2)}" if uname else "NoUsername"
                msg += (
                    f"• *User ID:* `{u_id}`\n"
                    f"  *Full Name:* {full_name_esc}\n"
                    f"  *Username:* {username_esc}\n"
                    f"  *Warnings in this group:* `{w_count}`\n\n"
                )

        try:
            # Telegram has a message length limit (4096 characters)
            if len(msg) > 4000:
                for i in range(0, len(msg), 4000):
                    await update.message.reply_text(
                        msg[i:i+4000],
                        parse_mode='MarkdownV2'
                    )
            else:
                await update.message.reply_text(
                    msg,
                    parse_mode='MarkdownV2'
                )
            logger.info("Displayed warnings information.")
        except Exception as e:
            logger.error(f"Error sending warnings information: {e}")
            await update.message.reply_text(
                "⚠️ An error occurred while sending the warnings information.",
                parse_mode='MarkdownV2'
            )
    except Exception as e:
        logger.error(f"Error processing /info command: {e}")
        await update.message.reply_text(
            "⚠️ Failed to retrieve warnings information. Please try again later.",
            parse_mode='MarkdownV2'
        )

async def get_id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /get_id command to retrieve chat or user IDs.
    Restricted to SUPER_ADMIN only.
    """
    user = update.effective_user
    logger.debug(f"/get_id command called by user {user.id}")
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /get_id by user {user.id}")
        return
    chat = update.effective_chat
    user_id = user.id
    try:
        if chat.type in ["group", "supergroup"]:
            await update.message.reply_text(
                f"🔢 *Group ID:* `{chat.id}`",
                parse_mode='MarkdownV2'
            )
            logger.info(f"Retrieved Group ID {chat.id} in group chat by SUPER_ADMIN {user.id}")
        else:
            await update.message.reply_text(
                f"🔢 *Your User ID:* `{user_id}`",
                parse_mode='MarkdownV2'
            )
            logger.info(f"Retrieved User ID {user_id} in private chat by SUPER_ADMIN")
    except Exception as e:
        logger.error(f"Error handling /get_id command: {e}")
        await update.message.reply_text(
            "⚠️ An error occurred while processing the command.",
            parse_mode='MarkdownV2'
        )

async def be_sad_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /be_sad command to activate Arabic text deletion in a group.
    Usage: /be_sad <group_id>
    """
    user = update.effective_user
    logger.debug(f"/be_sad command called by user {user.id} with args: {context.args}")
    
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /be_sad by user {user.id}")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text(
            "⚠️ Usage: `/be_sad <group_id>`",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /be_sad by SUPER_ADMIN {user.id}")
        return
    
    try:
        group_id = int(context.args[0])
        logger.debug(f"Parsed group_id: {group_id}")
    except ValueError:
        await update.message.reply_text(
            "⚠️ `group_id` must be an integer.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer group_id provided to /be_sad by SUPER_ADMIN {user.id}")
        return
    
    if not group_exists(group_id):
        await update.message.reply_text(
            "⚠️ Group not found.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Attempted to activate Arabic deletion for non-existent group {group_id} by SUPER_ADMIN {user.id}")
        return
    
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('UPDATE groups SET arabic_deletion_enabled = 1 WHERE group_id = ?', (group_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text(
            f"✅ Arabic text deletion activated for group `<code>{group_id}</code>`.",
            parse_mode='HTML'
        )
        logger.info(f"Activated Arabic text deletion for group {group_id} by SUPER_ADMIN {user.id}")
    except Exception as e:
        await update.message.reply_text(
            "⚠️ Failed to activate Arabic text deletion. Please try again later.",
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error activating Arabic text deletion for group {group_id} by SUPER_ADMIN {user.id}: {e}")

async def be_sad_off_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /be_sad_off command to deactivate Arabic text deletion in a group.
    Usage: /be_sad_off <group_id>
    """
    user = update.effective_user
    logger.debug(f"/be_sad_off command called by user {user.id} with args: {context.args}")
    
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /be_sad_off by user {user.id}")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text(
            "⚠️ Usage: `/be_sad_off <group_id>`",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /be_sad_off by SUPER_ADMIN {user.id}")
        return
    
    try:
        group_id = int(context.args[0])
        logger.debug(f"Parsed group_id: {group_id}")
    except ValueError:
        await update.message.reply_text(
            "⚠️ `group_id` must be an integer.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer group_id provided to /be_sad_off by SUPER_ADMIN {user.id}")
        return
    
    if not group_exists(group_id):
        await update.message.reply_text(
            "⚠️ Group not found.",
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Attempted to deactivate Arabic deletion for non-existent group {group_id} by SUPER_ADMIN {user.id}")
        return
    
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('UPDATE groups SET arabic_deletion_enabled = 0 WHERE group_id = ?', (group_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text(
            f"✅ Arabic text deletion deactivated for group `<code>{group_id}</code>`.",
            parse_mode='HTML'
        )
        logger.info(f"Deactivated Arabic text deletion for group {group_id} by SUPER_ADMIN {user.id}")
    except Exception as e:
        await update.message.reply_text(
            "⚠️ Failed to deactivate Arabic text deletion. Please try again later.",
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error deactivating Arabic text deletion for group {group_id} by SUPER_ADMIN {user.id}: {e}")

async def handle_warnings_with_arabic_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Enhanced handle_warnings function that also handles Arabic text deletion.
    """
    # First, handle warnings as usual
    await handle_warnings(update, context)
    
    # Now, handle Arabic text deletion
    chat = update.effective_chat
    message = update.message
    user = update.effective_user

    if chat.type not in ["group", "supergroup"]:
        return  # Only handle group messages

    group_id = chat.id

    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT arabic_deletion_enabled FROM groups WHERE group_id = ?', (group_id,))
        result = c.fetchone()
        conn.close()
        if result and result[0] == 1:
            # Arabic deletion is enabled for this group
            text = message.text or ""
            if await check_arabic(text):
                if not is_bypass_user(user.id):
                    try:
                        await message.delete()
                        logger.info(f"Deleted Arabic message from user {user.id} in group {group_id}")
                    except Exception as e:
                        logger.error(f"Failed to delete message from user {user.id} in group {group_id}: {e}")
    except Exception as e:
        logger.error(f"Error processing Arabic deletion for group {group_id}: {e}")

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

async def info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /info command to show warnings information.
    """
    user = update.effective_user
    user_id = user.id
    logger.debug(f"/info command called by user {user_id}")

    try:
        if user_id == SUPER_ADMIN_ID or is_global_tara(user_id):
            # Super Admin or Global TARA can see all warnings
            query = '''
                SELECT g.group_id, g.group_name, u.user_id, u.first_name, u.last_name, u.username, COUNT(w.id)
                FROM warnings_history w
                JOIN users u ON w.user_id = u.user_id
                JOIN groups g ON w.group_id = g.group_id
                GROUP BY g.group_id, u.user_id
                ORDER BY g.group_id, COUNT(w.id) DESC
            '''
            params = ()
        elif is_normal_tara(user_id):
            # Normal TARA can see warnings in linked groups
            linked_groups = get_linked_groups_for_tara(user_id)
            if not linked_groups:
                await update.message.reply_text(
                    "⚠️ No linked groups or permission.",
                    parse_mode='MarkdownV2'
                )
                logger.debug(f"TARA {user_id} has no linked groups.")
                return
            placeholders = ','.join('?' for _ in linked_groups)
            query = f'''
                SELECT g.group_id, g.group_name, u.user_id, u.first_name, u.last_name, u.username, COUNT(w.id)
                FROM warnings_history w
                JOIN users u ON w.user_id = u.user_id
                JOIN groups g ON w.group_id = g.group_id
                WHERE w.group_id IN ({placeholders})
                GROUP BY g.group_id, u.user_id
                ORDER BY g.group_id, COUNT(w.id) DESC
            '''
            params = linked_groups
        else:
            await update.message.reply_text(
                "⚠️ You don't have permission to view warnings.",
                parse_mode='MarkdownV2'
            )
            logger.warning(f"User {user_id} attempted to use /info without permissions.")
            return

        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()

        if not rows:
            await update.message.reply_text(
                "⚠️ No warnings found.",
                parse_mode='MarkdownV2'
            )
            logger.debug("No warnings found to display.")
            return

        from collections import defaultdict
        group_data = defaultdict(list)
        for g_id, g_name, u_id, f_name, l_name, uname, w_count in rows:
            group_data[g_id].append((g_name, u_id, f_name, l_name, uname, w_count))

        msg = "*Warnings Information:*\n\n"
        for g_id, info_list in group_data.items():
            group_name = info_list[0][0] if info_list[0][0] else "No Name"
            group_name_esc = escape_markdown(group_name, version=2)
            msg += f"*Group:* {group_name_esc}\n*Group ID:* `{g_id}`\n"
            for (_, u_id, f_name, l_name, uname, w_count) in info_list:
                full_name = (f"{f_name or ''} {l_name or ''}".strip() or "N/A")
                full_name_esc = escape_markdown(full_name, version=2)
                username_esc = f"@{escape_markdown(uname, version=2)}" if uname else "NoUsername"
                msg += (
                    f"• *User ID:* `{u_id}`\n"
                    f"  *Full Name:* {full_name_esc}\n"
                    f"  *Username:* {username_esc}\n"
                    f"  *Warnings in this group:* `{w_count}`\n\n"
                )

        try:
            # Telegram has a message length limit (4096 characters)
            if len(msg) > 4000:
                for i in range(0, len(msg), 4000):
                    await update.message.reply_text(
                        msg[i:i+4000],
                        parse_mode='MarkdownV2'
                    )
            else:
                await update.message.reply_text(
                    msg,
                    parse_mode='MarkdownV2'
                )
            logger.info("Displayed warnings information.")
        except Exception as e:
            logger.error(f"Error sending warnings information: {e}")
            await update.message.reply_text(
                "⚠️ An error occurred while sending the warnings information.",
                parse_mode='MarkdownV2'
            )
    except Exception as e:
        logger.error(f"Error processing /info command: {e}")
        await update.message.reply_text(
            "⚠️ Failed to retrieve warnings information. Please try again later.",
            parse_mode='MarkdownV2'
        )

async def be_sad_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /be_sad command to activate Arabic text deletion in a group.
    Usage: /be_sad <group_id>
    """
    # Implementation already provided above
    pass  # Placeholder since function is defined earlier

async def be_sad_off_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /be_sad_off command to deactivate Arabic text deletion in a group.
    Usage: /be_sad_off <group_id>
    """
    # Implementation already provided above
    pass  # Placeholder since function is defined earlier

async def test_arabic_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /test_arabic command to test Arabic detection.
    Usage: /test_arabic <text>
    """
    text = ' '.join(context.args)
    logger.debug(f"/test_arabic command called with text: {text}")
    if not text:
        await update.message.reply_text(
            "⚠️ Usage: `/test_arabic <text>`",
            parse_mode='MarkdownV2'
        )
        return
    try:
        result = await check_arabic(text)
        await update.message.reply_text(
            f"✅ Contains Arabic: `<code>{result}</code>`",
            parse_mode='HTML'
        )
        logger.debug(f"Arabic detection for '{text}': {result}")
    except Exception as e:
        logger.error(f"Error processing /test_arabic command: {e}")
        await update.message.reply_text(
            "⚠️ An error occurred while processing the command.",
            parse_mode='MarkdownV2'
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle errors that occur during updates.
    """
    logger.error("An error occurred:", exc_info=context.error)

def main():
    """
    Main function to initialize the bot and register handlers.
    """
    try:
        init_db()
    except Exception as e:
        logger.critical(f"Bot cannot start due to database initialization failure: {e}")
        return

    TOKEN = os.getenv('BOT_TOKEN')
    if not TOKEN:
        logger.error("⚠️ BOT_TOKEN is not set.")
        return
    TOKEN = TOKEN.strip()
    if TOKEN.lower().startswith('bot='):
        TOKEN = TOKEN[len('bot='):].strip()
        logger.warning("BOT_TOKEN should not include 'bot=' prefix. Stripping it.")

    try:
        application = ApplicationBuilder().token(TOKEN).build()
    except Exception as e:
        logger.critical(f"Failed to build the application with the provided TOKEN: {e}")
        return

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("set", set_warnings_cmd))
    application.add_handler(CommandHandler("tara_G", tara_g_cmd))
    application.add_handler(CommandHandler("rmove_G", remove_global_tara_cmd))
    application.add_handler(CommandHandler("tara", tara_cmd))
    application.add_handler(CommandHandler("rmove_t", remove_normal_tara_cmd))
    application.add_handler(CommandHandler("unlink_tara", unlink_tara_cmd))
    application.add_handler(CommandHandler("group_add", group_add_cmd))
    application.add_handler(CommandHandler("rmove_group", rmove_group_cmd))
    application.add_handler(CommandHandler("tara_link", tara_link_cmd))
    application.add_handler(CommandHandler("bypass", bypass_cmd))
    application.add_handler(CommandHandler("unbypass", unbypass_cmd))
    application.add_handler(CommandHandler("show", show_groups_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("get_id", get_id_cmd))
    application.add_handler(CommandHandler("be_sad", be_sad_cmd))
    application.add_handler(CommandHandler("be_sad_off", be_sad_off_cmd))
    application.add_handler(CommandHandler("test_arabic", test_arabic_cmd))
    
    # Handle private messages for setting group name
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        handle_private_message_for_group_name
    ))

    # Handle group messages for issuing warnings and Arabic deletion
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP),
        handle_warnings_with_arabic_deletion
    ))

    # Register error handler
    application.add_error_handler(error_handler)

    logger.info("🚀 Bot starting...")
    try:
        application.run_polling()
    except Exception as e:
        logger.critical(f"Bot encountered a critical error and is shutting down: {e}")

if __name__ == '__main__':
    main()
