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
from telegram.helpers import escape_markdown
from telegram.error import Forbidden

from warning_handler import handle_warnings  # Renamed file to avoid conflicts

DATABASE = 'warnings.db'

# SUPER_ADMIN who can use restricted commands
SUPER_ADMIN_ID = 6177929931  # Replace with your actual super admin user ID

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
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
    # Add group_id column if not exists
    try:
        c.execute('ALTER TABLE warnings_history ADD COLUMN group_id INTEGER')
    except:
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

    conn.commit()
    conn.close()

def load_admin_ids():
    try:
        with open('Tara_access.txt', 'r') as file:
            admin_ids = [int(line.strip()) for line in file if line.strip().isdigit()]
        logger.info(f"Loaded admin IDs: {admin_ids}")
        return admin_ids
    except FileNotFoundError:
        logger.warning("Tara_access.txt not found. No global TARA admins.")
        return []
    except ValueError as e:
        logger.error(f"Error parsing admin IDs: {e}")
        return []

def save_admin_id(new_admin_id):
    try:
        with open('Tara_access.txt', 'a') as file:
            file.write(f"{new_admin_id}\n")
        logger.info(f"Added new admin ID: {new_admin_id}")
    except Exception as e:
        logger.error(f"Error saving admin ID {new_admin_id}: {e}")

def remove_admin_id(tara_id):
    try:
        if not os.path.exists('Tara_access.txt'):
            return False
        with open('Tara_access.txt', 'r') as file:
            lines = file.readlines()
        new_lines = [line for line in lines if line.strip() != str(tara_id)]
        if len(new_lines) == len(lines):
            return False
        with open('Tara_access.txt', 'w') as file:
            file.writelines(new_lines)
        logger.info(f"Removed TARA admin ID: {tara_id}")
        return True
    except Exception as e:
        logger.error(f"Error removing admin ID {tara_id}: {e}")
        return False

def group_exists(group_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT 1 FROM groups WHERE group_id = ?', (group_id,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

def add_group(group_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO groups (group_id, group_name) VALUES (?, ?)', (group_id, None))
    conn.commit()
    conn.close()

def set_group_name(g_id, group_name):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('UPDATE groups SET group_name = ? WHERE group_id = ?', (group_name, g_id))
    conn.commit()
    conn.close()

def link_tara_to_group(tara_id, g_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('INSERT INTO tara_links (tara_user_id, group_id) VALUES (?, ?)', (tara_id, g_id))
    conn.commit()
    conn.close()

def get_group_taras(g_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT tara_user_id FROM tara_links WHERE group_id = ?', (g_id,))
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

async def handle_private_message_for_group_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This handler only for private chats
    if update.effective_chat.type != "private":
        return

    message = update.message
    user = message.from_user

    if user.id == SUPER_ADMIN_ID and user.id in pending_group_names:
        g_id = pending_group_names.pop(user.id)
        group_name = message.text.strip()
        set_group_name(g_id, group_name)
        await message.reply_text(f"Group name for {g_id} set to: {group_name}")
        logger.info(f"Group name for {g_id} saved as {group_name}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is running.")
    logger.info(f"/start from {update.effective_user.id}, chat_id={update.effective_chat.id}, type={update.effective_chat.type}")

async def set_warnings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text("You don't have permission.")
        return
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Usage: /set <user_id> <number>")
        return
    try:
        target_user_id = int(args[0])
        new_warnings = int(args[1])
    except ValueError:
        await update.message.reply_text("Integers required.")
        return
    if new_warnings < 0:
        await update.message.reply_text("No negative warnings.")
        return
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO warnings (user_id, warnings) 
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET 
            warnings=excluded.warnings
    ''', (target_user_id, new_warnings))
    conn.commit()
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    c.execute('''
        INSERT INTO warnings_history (user_id, warning_number, timestamp, group_id)
        VALUES (?, ?, ?, NULL)
    ''', (target_user_id, new_warnings, timestamp))
    conn.commit()
    conn.close()

    try:
        await context.bot.send_message(chat_id=target_user_id, text=f"Your warnings set to {new_warnings}.", parse_mode='Markdown')
    except Forbidden:
        logger.warning(f"Couldn't send PM to user {target_user_id}")
    await update.message.reply_text(f"Set {new_warnings} warnings for user {target_user_id}.")

async def add_tara_admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text("No permission.")
        return
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Usage: /tara <admin_id>")
        return
    try:
        new_admin_id = int(args[0])
    except ValueError:
        await update.message.reply_text("Integer required.")
        return
    admin_ids = load_admin_ids()
    if new_admin_id in admin_ids:
        await update.message.reply_text("Already an admin.")
        return
    save_admin_id(new_admin_id)
    await update.message.reply_text(f"Added TARA admin {new_admin_id}.")

async def remove_tara_admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text("No permission.")
        return
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Usage: /rmove <tara_id>")
        return
    try:
        tara_id = int(args[0])
    except ValueError:
        await update.message.reply_text("Integer required.")
        return
    if remove_admin_id(tara_id):
        await update.message.reply_text(f"Removed TARA {tara_id}.")
    else:
        await update.message.reply_text(f"TARA {tara_id} not found.")

async def group_add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text("No permission.")
        return
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Usage: /group_add <group_id>")
        return
    try:
        group_id = int(args[0])
    except ValueError:
        await update.message.reply_text("Integer required.")
        return

    if group_exists(group_id):
        await update.message.reply_text("Group already added.")
        return

    add_group(group_id)
    pending_group_names[user.id] = group_id
    logger.info(f"Group {group_id} added, awaiting name from SUPER_ADMIN in private chat.")
    await update.message.reply_text(f"Group {group_id} added. Send the group name in private chat now.")

async def tara_link_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text("No permission.")
        return
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Usage: /tara_link <tara_id> <group_id>")
        return
    try:
        tara_id = int(args[0])
        g_id = int(args[1])
    except ValueError:
        await update.message.reply_text("Integers required.")
        return
    if not group_exists(g_id):
        await update.message.reply_text("Group not added.")
        return
    link_tara_to_group(tara_id, g_id)
    await update.message.reply_text(f"Linked TARA {tara_id} to group {g_id}.")

async def show_groups_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text("No permission.")
        return

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT group_id, group_name FROM groups')
    groups_data = c.fetchall()
    conn.close()

    if not groups_data:
        await update.message.reply_text("No groups added.")
        return

    msg = "*Groups Information:*\n\n"
    for g_id, g_name in groups_data:
        g_name_esc = escape_markdown(g_name if g_name else "No Name Set", version=2)
        msg += f"• *Group ID:* `{g_id}`\n"
        msg += f"  *Name:* {g_name_esc}\n"
        taras = get_group_taras(g_id)
        if taras:
            msg += "  *TARAs linked:*\n"
            for t_id in taras:
                msg += f"    • `{t_id}`\n"
        else:
            msg += "  No TARAs linked.\n"
        msg += "\n"

    await update.message.reply_text(msg, parse_mode='MarkdownV2')

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text("No permission.")
        return

    help_text = """*Available Commands (SUPER_ADMIN only):*
/start - Check if bot is running
/set <user_id> <number> - Set warnings for a user
/tara <admin_id> - Add a TARA admin ID
/rmove <tara_id> - Remove a TARA admin ID
/group_add <group_id> - Register a group (use exact chat_id)
  Then send the group name in private chat
/tara_link <tara_id> <group_id> - Link a TARA admin to a group
/show - Show all groups and linked TARAs
/help - Show this help
/info - Show warnings info (SUPER_ADMIN sees all, TARA sees linked groups)
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    logger.info(f"/info command from {user_id}")
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    if user_id == SUPER_ADMIN_ID:
        c.execute('''
            SELECT g.group_id, g.group_name, u.user_id, u.first_name, u.last_name, u.username, COUNT(w.id)
            FROM warnings_history w
            JOIN users u ON w.user_id = u.user_id
            JOIN groups g ON w.group_id = g.group_id
            GROUP BY g.group_id, u.user_id
            ORDER BY g.group_id, COUNT(w.id) DESC
        ''')
    else:
        c.execute('SELECT group_id FROM tara_links WHERE tara_user_id = ?', (user_id,))
        linked_groups = [row[0] for row in c.fetchall()]

        if not linked_groups:
            conn.close()
            await update.message.reply_text("No permission or no linked groups.")
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
        c.execute(query, linked_groups)

    rows = c.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("No warnings found.")
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

    await update.message.reply_text(msg, parse_mode='MarkdownV2')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error("An error occurred:", exc_info=context.error)

def main():
    init_db()
    TOKEN = os.getenv('BOT_TOKEN')
    if not TOKEN:
        logger.error("BOT_TOKEN is not set. Set it as an environment variable or directly in code.")
        return
    TOKEN = TOKEN.strip()
    if TOKEN.lower().startswith('bot='):
        TOKEN = TOKEN[len('bot='):].strip()

    application = ApplicationBuilder().token(TOKEN).build()

    # Command Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("set", set_warnings_cmd))
    application.add_handler(CommandHandler("tara", add_tara_admin_cmd))
    application.add_handler(CommandHandler("rmove", remove_tara_admin_cmd))
    application.add_handler(CommandHandler("group_add", group_add_cmd))
    application.add_handler(CommandHandler("tara_link", tara_link_cmd))
    application.add_handler(CommandHandler("show", show_groups_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("info", info_cmd))

    # Message handlers
    # Private messages only for setting group name
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_private_message_for_group_name))
    # Group messages for issuing warnings
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & (filters.ChatType.GROUPS | filters.ChatType.SUPERGROUP), handle_warnings))

    # Add error handler
    application.add_error_handler(error_handler)

    logger.info("Bot starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
