import os
import re
import sqlite3
import logging
from datetime import datetime
from telegram import Update, Chat
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)
from telegram.error import Forbidden
from telegram.helpers import escape_markdown

DATABASE = 'warnings.db'

# SUPER_ADMIN who can use restricted commands
SUPER_ADMIN_ID = 6177929931  # Replace with your actual super admin user ID

REGULATIONS_MESSAGE = """
*Communication Channels Regulation*

The Official Groups and channels have been created to facilitate communication between  
students and officials. Here are the regulations:
• The official language of the group is *ENGLISH ONLY*
• Avoid any side discussions by any means.
• When having a general request or question, send it to the group and tag the related official (TARA or others).
• Messages should be sent in official working hours (8:00 AM to 5:00 PM), and only important questions/inquiries after these hours.

Not complying with the above regulations will result in:
1- Primary warning.
2- Second warning.
3- Third warning may be addressed to DISCIPLINARY COMMITTEE.
"""

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

def is_arabic(text):
    return bool(re.search(r'[\u0600-\u06FF]', text))

def get_user_warnings(user_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT warnings FROM warnings WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def update_warnings(user_id, warnings):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO warnings (user_id, warnings) 
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET 
            warnings=excluded.warnings
    ''', (user_id, warnings))
    conn.commit()
    conn.close()

def log_warning(user_id, warning_number, group_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    c.execute('''
        INSERT INTO warnings_history (user_id, warning_number, timestamp, group_id)
        VALUES (?, ?, ?, ?)
    ''', (user_id, warning_number, timestamp, group_id))
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

def update_user_info(user):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO users (user_id, first_name, last_name, username)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            first_name=excluded.first_name,
            last_name=excluded.last_name,
            username=excluded.username
    ''', (user.id, user.first_name, user.last_name, user.username))
    conn.commit()
    conn.close()

def group_exists(group_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT group_id, group_name FROM groups')
    all_groups = c.fetchall()
    logger.info(f"Checking group_exists for {group_id}. All groups in DB: {all_groups}")
    c.execute('SELECT 1 FROM groups WHERE group_id = ?', (group_id,))
    exists = c.fetchone() is not None
    logger.info(f"group_exists({group_id}) = {exists}")
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

async def handle_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return

    user = message.from_user
    chat = message.chat

    if chat.type not in ['group', 'supergroup']:
        return

    logger.info(f"Received message in group {chat.id} from {user.id}: {message.text}")
    g_id = int(chat.id)

    if not group_exists(g_id):
        logger.info("This group is not registered. No action taken.")
        return

    # Group registered
    update_user_info(user)

    if is_arabic(message.text):
        warnings_count = get_user_warnings(user.id) + 1
        logger.info(f"User {user.id} posted Arabic. Warnings now: {warnings_count}")

        if warnings_count == 1:
            reason = "1- Primary warning sent to the student."
        elif warnings_count == 2:
            reason = "2- Second warning sent to the student."
        else:
            reason = "3- Third warning sent to the student. May be addressed to DISCIPLINARY COMMITTEE."

        update_warnings(user.id, warnings_count)
        log_warning(user.id, warnings_count, g_id)

        # Send PM to user
        try:
            alarm_message = f"{REGULATIONS_MESSAGE}\n\n{reason}"
            await context.bot.send_message(chat_id=user.id, text=alarm_message, parse_mode='Markdown')
            logger.info(f"Alarm message sent to user {user.id} in private.")
            user_notification = "✅ Alarm sent to user."
        except Forbidden:
            logger.error(f"Cannot send private message to user {user.id}. They must start the bot in private first.")
            user_notification = "⚠️ User has not started the bot."
        except Exception as e:
            logger.error(f"Error sending private message to user {user.id}: {e}")
            user_notification = f"⚠️ Error sending alarm: {e}"

        # Notify TARAs
        admin_ids = load_admin_ids()
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT first_name, last_name, username FROM users WHERE user_id = ?', (user.id,))
        user_info = c.fetchone()
        conn.close()

        if user_info:
            first_name, last_name, username_ = user_info
            full_name = (f"{first_name or ''} {last_name or ''}").strip() or "N/A"
        else:
            full_name = "N/A"
            username_ = None

        full_name_esc = escape_markdown(full_name, version=2)
        username_display = f"@{escape_markdown(username_, version=2)}" if username_ else "NoUsername"
        reason_esc = escape_markdown(reason, version=2)

        alarm_report = (
            f"*Alarm Report*\n"
            f"*Student ID:* `{user.id}`\n"
            f"*Full Name:* {full_name_esc}\n"
            f"*Username:* {username_display}\n"
            f"*Number of Warnings:* `{warnings_count}`\n"
            f"*Reason:* {reason_esc}\n"
            f"*Date:* `{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC`\n"
            f"{escape_markdown(user_notification, version=2)}\n"
        )

        # Send to global TARAs
        for admin_id in admin_ids:
            try:
                await context.bot.send_message(chat_id=admin_id, text=alarm_report, parse_mode='MarkdownV2')
                logger.info(f"Sent report to global TARA {admin_id}")
            except Exception as e:
                logger.error(f"Error sending to admin {admin_id}: {e}")

        # Send to TARAs linked to this group
        group_taras = get_group_taras(g_id)
        for t_id in group_taras:
            if t_id not in admin_ids:
                try:
                    await context.bot.send_message(chat_id=t_id, text=alarm_report, parse_mode='MarkdownV2')
                    logger.info(f"Sent report to linked TARA {t_id}")
                except Exception as e:
                    logger.error(f"Error sending to group TARA {t_id}: {e}")

async def handle_private_message_for_group_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user = message.from_user
    chat = message.chat

    # Only proceed if this is a private chat
    if chat.type != "private":
        return

    logger.info(f"Private message from {user.id} in {chat.id}: {message.text}, pending: {pending_group_names}")

    if user.id == SUPER_ADMIN_ID and user.id in pending_group_names:
        g_id = pending_group_names.pop(user.id)
        group_name = message.text.strip()
        set_group_name(g_id, group_name)
        await message.reply_text(f"Group name for {g_id} set to: {group_name}")
        logger.info(f"Group name for {g_id} saved as {group_name}")
    else:
        logger.info("No group name pending or not SUPER_ADMIN private chat.")

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
    update_warnings(target_user_id, new_warnings)
    log_warning(target_user_id, new_warnings, None)
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
    admin_ids = load_admin_ids()

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
        group_name = info_list[0][0]
        g_name_esc = escape_markdown(group_name if group_name else "No Name", version=2)
        msg += f"*Group:* {g_name_esc}\n*Group ID:* `{g_id}`\n"
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

    # Message Handlers
    # Handle private messages for setting group name
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_private_message_for_group_name))
    # Handle group messages for issuing warnings
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_group_messages))

    logger.info("Bot starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
