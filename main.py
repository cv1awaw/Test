# main.py

import os
import sqlite3
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)
from telegram.constants import ChatType
from telegram.helpers import escape_markdown

from warning_handler import handle_warnings, check_arabic  # Ensure correct import

DATABASE = 'warnings.db'

# Replace with your actual SUPER_ADMIN_ID (integer)
SUPER_ADMIN_ID = 6177929931  # Example: 123456789

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  # Set to DEBUG for detailed logs
)
logger = logging.getLogger(__name__)

pending_group_names = {}

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS warnings (
            user_id INTEGER PRIMARY KEY,
            warnings INTEGER NOT NULL DEFAULT 0
        )
    ''')
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
    # Add group_id column if not already exists
    try:
        c.execute('ALTER TABLE warnings_history ADD COLUMN group_id INTEGER')
    except sqlite3.OperationalError:
        pass

    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            username TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            group_id INTEGER PRIMARY KEY,
            group_name TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS tara_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tara_user_id INTEGER NOT NULL,
            group_id INTEGER NOT NULL,
            FOREIGN KEY(group_id) REFERENCES groups(group_id)
        )
    ''')

    # Global TARAs
    c.execute('''
        CREATE TABLE IF NOT EXISTS global_taras (
            tara_id INTEGER PRIMARY KEY
        )
    ''')

    # Normal TARAs
    c.execute('''
        CREATE TABLE IF NOT EXISTS normal_taras (
            tara_id INTEGER PRIMARY KEY
        )
    ''')

    # Bypass Users
    c.execute('''
        CREATE TABLE IF NOT EXISTS bypass_users (
            user_id INTEGER PRIMARY KEY
        )
    ''')

    conn.commit()
    conn.close()
    logger.debug("Database initialized.")

def group_exists(group_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT 1 FROM groups WHERE group_id = ?', (group_id,))
    exists = c.fetchone() is not None
    conn.close()
    logger.debug(f"Checked existence of group {group_id}: {exists}")
    return exists

def add_group(group_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO groups (group_id, group_name) VALUES (?, ?)', (group_id, None))
    conn.commit()
    conn.close()
    logger.info(f"Added group {group_id} to database with no name.")

def set_group_name(g_id, group_name):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('UPDATE groups SET group_name = ? WHERE group_id = ?', (group_name, g_id))
    conn.commit()
    conn.close()
    logger.info(f"Set name for group {g_id}: {group_name}")

def link_tara_to_group(tara_id, g_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('INSERT INTO tara_links (tara_user_id, group_id) VALUES (?, ?)', (tara_id, g_id))
    conn.commit()
    conn.close()
    logger.info(f"Linked TARA {tara_id} to group {g_id}")

def add_global_tara(tara_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO global_taras (tara_id) VALUES (?)', (tara_id,))
    conn.commit()
    conn.close()
    logger.info(f"Added global TARA {tara_id}")

def remove_global_tara(tara_id):
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

def add_normal_tara(tara_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO normal_taras (tara_id) VALUES (?)', (tara_id,))
    conn.commit()
    conn.close()
    logger.info(f"Added normal TARA {tara_id}")

def remove_normal_tara(tara_id):
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

def is_global_tara(user_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT 1 FROM global_taras WHERE tara_id = ?', (user_id,))
    res = c.fetchone() is not None
    conn.close()
    logger.debug(f"Checked if user {user_id} is a global TARA: {res}")
    return res

def is_normal_tara(user_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT 1 FROM normal_taras WHERE tara_id = ?', (user_id,))
    res = c.fetchone() is not None
    conn.close()
    logger.debug(f"Checked if user {user_id} is a normal TARA: {res}")
    return res

def get_linked_groups_for_tara(user_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT group_id FROM tara_links WHERE tara_user_id = ?', (user_id,))
    rows = c.fetchall()
    conn.close()
    groups = [r[0] for r in rows]
    logger.debug(f"TARA {user_id} is linked to groups: {groups}")
    return groups

def is_bypass_user(user_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT 1 FROM bypass_users WHERE user_id = ?', (user_id,))
    res = c.fetchone() is not None
    conn.close()
    logger.debug(f"Checked if user {user_id} is bypassed: {res}")
    return res

def add_bypass_user(user_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO bypass_users (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()
    logger.info(f"Added user {user_id} to bypass list.")

def remove_bypass_user(user_id):
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

async def handle_private_message_for_group_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != ChatType.PRIVATE:
        return
    message = update.message
    user = message.from_user
    logger.debug(f"Received private message from user {user.id}: {message.text}")
    if user.id == SUPER_ADMIN_ID and user.id in pending_group_names:
        g_id = pending_group_names.pop(user.id)
        group_name = message.text.strip()
        if group_name:
            set_group_name(g_id, group_name)
            escaped_group_name = escape_markdown(group_name, version=2)
            await message.reply_text(f"✅ Group name for `{g_id}` set to: *{escaped_group_name}*", parse_mode='MarkdownV2')
            logger.info(f"Group name for {g_id} set to {group_name} by SUPER_ADMIN {user.id}")
        else:
            await message.reply_text("⚠️ Group name cannot be empty. Please try `/group_add` again.", parse_mode='MarkdownV2')
            logger.warning(f"Empty group name received from SUPER_ADMIN {user.id} for group {g_id}")
    else:
        await message.reply_text("⚠️ No pending group to set name for.", parse_mode='MarkdownV2')
        logger.warning(f"Received group name from user {user.id} with no pending group.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is running and ready.", parse_mode='MarkdownV2')
    logger.info(f"/start called by user {update.effective_user.id}")

async def set_warnings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.debug(f"/set command called by user {user.id} with args: {context.args}")
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text("❌ You don't have permission to use this command.", parse_mode='MarkdownV2')
        logger.warning(f"Unauthorized access attempt to /set by user {user.id}")
        return
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("⚠️ Usage: `/set <user_id> <number>`", parse_mode='MarkdownV2')
        logger.warning(f"Incorrect usage of /set by SUPER_ADMIN {user.id}")
        return
    try:
        target_user_id = int(args[0])
        new_warnings = int(args[1])
    except ValueError:
        await update.message.reply_text("⚠️ Both `user_id` and `number` must be integers.", parse_mode='MarkdownV2')
        logger.warning(f"Non-integer arguments provided to /set by SUPER_ADMIN {user.id}")
        return
    if new_warnings < 0:
        await update.message.reply_text("⚠️ Number of warnings cannot be negative.", parse_mode='MarkdownV2')
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

        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"🔧 Your number of warnings has been set to `{new_warnings}` by the administrator.",
                parse_mode='MarkdownV2'
            )
            logger.info(f"Sent warning update to user {target_user_id}")
        except Forbidden:
            logger.error(f"Cannot send warning update to user {target_user_id}. They might not have started the bot.")
        except Exception as e:
            logger.error(f"Error sending warning update to user {target_user_id}: {e}")

        await update.message.reply_text(f"✅ Set `{new_warnings}` warnings for user ID `{target_user_id}`.", parse_mode='MarkdownV2')
        logger.debug(f"Responded to /set command by SUPER_ADMIN {user.id}")
    except sqlite3.Error as db_err:
        logger.error(f"Database error in /set command: {db_err}", exc_info=True)
        await update.message.reply_text(
            "⚠️ A database error occurred while setting warnings.", 
            parse_mode='MarkdownV2'
        )
    except Exception as e:
        logger.error(f"Unexpected error in /set command: {e}", exc_info=True)
        await update.message.reply_text(
            "⚠️ An unexpected error occurred while setting warnings.", 
            parse_mode='MarkdownV2'
        )

# ... [Other command handlers remain unchanged] ...

async def tara_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    except ValueError as ve:
        await update.message.reply_text(
            "⚠️ `tara_id` must be an integer.", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer tara_id provided to /tara by SUPER_ADMIN {user.id}: {context.args[0]}")
        return
    
    try:
        add_normal_tara(tara_id)
        escaped_tara_id = escape_markdown(str(tara_id), version=2)
        await update.message.reply_text(
            f"✅ Added normal TARA `{escaped_tara_id}`.", 
            parse_mode='MarkdownV2'
        )
        logger.info(f"Added normal TARA {tara_id} by SUPER_ADMIN {user.id}")
    except sqlite3.Error as db_err:
        logger.error(f"Database error in /tara command: {db_err}", exc_info=True)
        await update.message.reply_text(
            "⚠️ A database error occurred while adding the normal TARA.", 
            parse_mode='MarkdownV2'
        )
    except Exception as e:
        logger.error(f"Unexpected error in /tara command: {e}", exc_info=True)
        await update.message.reply_text(
            "⚠️ An unexpected error occurred while adding the normal TARA.", 
            parse_mode='MarkdownV2'
        )
