import os
import re
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
from telegram.error import Forbidden
from telegram.helpers import escape_markdown

DATABASE = 'warnings.db'

# User ID who can use restricted commands
SUPER_ADMIN_ID = 6177929931  # Replace with the actual super admin Telegram user ID

REGULATIONS_MESSAGE = """
*Communication Channels Regulation*

The Official Groups and channels have been created to facilitate the communication between the  
students and the officials. Here are the regulations:
• The official language of the group is *ENGLISH ONLY*  
• Avoid any side discussions by any means. 
• When having a general request or question, send it to the group and tag the related official (TARA or other officials). 
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

# State dictionary for pending group name inputs: {user_id: group_id}
pending_group_names = {}

def init_db():
    """Initialize the SQLite database with required tables."""
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

    # Add group_id column to warnings_history if not exists
    # This may fail if the column already exists; ignore errors.
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
    if row:
        (warnings,) = row
        return warnings
    return 0

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
        logger.error("Tara_access.txt not found.")
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
        logger.error(f"Error saving new admin ID {new_admin_id}: {e}")

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

def set_group_name(group_id, group_name):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('UPDATE groups SET group_name = ? WHERE group_id = ?', (group_name, group_id))
    conn.commit()
    conn.close()

def link_tara_to_group(tara_id, group_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('INSERT INTO tara_links (tara_user_id, group_id) VALUES (?, ?)', (tara_id, group_id))
    conn.commit()
    conn.close()

def get_group_taras(group_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT tara_user_id FROM tara_links WHERE group_id = ?', (group_id,))
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return

    user = message.from_user

    # Check if we are in the middle of a group naming process
    if user.id == SUPER_ADMIN_ID and user.id in pending_group_names:
        group_id = pending_group_names.pop(user.id)
        group_name = message.text.strip()
        set_group_name(group_id, group_name)
        await message.reply_text(f"Group name for {group_id} set to: {group_name}")
        return

    chat = message.chat
    if chat.type not in ['group', 'supergroup']:
        return

    # If group not registered, do nothing
    if not group_exists(chat.id):
        return

    # Update user info
    update_user_info(user)

    if is_arabic(message.text):
        warnings_count = get_user_warnings(user.id) + 1
        logger.info(f"User {user.id} warnings: {warnings_count}")

        if warnings_count == 1:
            reason = "1- Primary warning sent to the student."
        elif warnings_count == 2:
            reason = "2- Second warning sent to the student."
        else:
            reason = "3- Third warning sent to the student. May be addressed to DISCIPLINARY COMMITTEE."

        update_warnings(user.id, warnings_count)
        log_warning(user.id, warnings_count, chat.id)

        # Send PM to user
        try:
            alarm_message = f"{REGULATIONS_MESSAGE}\n\n{reason}"
            await context.bot.send_message(
                chat_id=user.id,
                text=alarm_message,
                parse_mode='Markdown'
            )
            logger.info(f"Alarm message sent to user {user.id}")
            user_notification = "✅ Alarm sent to user."
        except Forbidden:
            logger.error("Cannot send private message to user.")
            user_notification = "⚠️ User has not started the bot."
        except Exception as e:
            logger.error(f"Error sending private message: {e}")
            user_notification = f"⚠️ Error sending alarm: {e}"

        # Notify admins
        admin_ids = load_admin_ids()

        # Fetch user info
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT first_name, last_name, username FROM users WHERE user_id = ?', (user.id,))
        user_info = c.fetchone()
        conn.close()

        if user_info:
            first_name, last_name, username = user_info
            full_name = (f"{first_name or ''} {last_name or ''}").strip() or "N/A"
        else:
            full_name = "N/A"
            username = None

        # Escape fields
        full_name_esc = escape_markdown(full_name, version=2)
        username_display = f"@{escape_markdown(username, version=2)}" if username else "NoUsername"
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
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=alarm_report,
                    parse_mode='MarkdownV2'
                )
            except Forbidden:
                logger.error(f"Cannot send to admin {admin_id}.")
            except Exception as e:
                logger.error(f"Error sending to admin {admin_id}: {e}")

        # Send to TARAs linked to this group
        group_taras = get_group_taras(chat.id)
        for t_id in group_taras:
            if t_id not in admin_ids:  # If not already notified as global admin
                try:
                    await context.bot.send_message(
                        chat_id=t_id,
                        text=alarm_report,
                        parse_mode='MarkdownV2'
                    )
                except Forbidden:
                    logger.error(f"Cannot send to group TARA {t_id}.")
                except Exception as e:
                    logger.error(f"Error sending to group TARA {t_id}: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is running.")
    logger.info(f"/start from {update.effective_user.id}")

async def set_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    # Notify user
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"Your warnings set to {new_warnings}.",
            parse_mode='Markdown'
        )
    except Forbidden:
        pass
    await update.message.reply_text(f"Set {new_warnings} warnings for user {target_user_id}.")

async def add_tara_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def remove_tara_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def group_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    await update.message.reply_text(f"Group {group_id} added. Send group name next.")

async def tara_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        group_id = int(args[1])
    except ValueError:
        await update.message.reply_text("Integers required.")
        return
    if not group_exists(group_id):
        await update.message.reply_text("Group not added.")
        return
    link_tara_to_group(tara_id, group_id)
    await update.message.reply_text(f"Linked TARA {tara_id} to group {group_id}.")

async def show_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    try:
        if len(msg) > 4000:
            for i in range(0, len(msg), 4000):
                await update.message.reply_text(msg[i:i+4000], parse_mode='MarkdownV2')
        else:
            await update.message.reply_text(msg, parse_mode='MarkdownV2')
    except Exception as e:
        logger.error(f"Error sending show message: {e}")
        await update.message.reply_text("Error displaying groups.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text("No permission.")
        return

    help_text = """*Available Commands (SUPER_ADMIN only):*
/start - Check if bot is running
/set <user_id> <number> - Set warnings for a user
/tara <admin_id> - Add a new TARA admin ID
/rmove <tara_id> - Remove a TARA admin ID
/group_add <group_id> - Add a group and then provide a name
/tara_link <tara_id> <group_id> - Link a TARA admin to a group
/show - Show all groups and linked TARAs
/help - Show this help message

*For TARA admins (listed in Tara_access.txt or linked):*
/info - Show warnings information:
   - SUPER_ADMIN sees all groups and warnings.
   - TARA sees only their linked groups' warnings.
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    admin_ids = load_admin_ids()

    # Determine permissions
    # If SUPER_ADMIN: show all warnings
    # Else if TARA: show only linked groups
    # Else: no permission
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    if user_id == SUPER_ADMIN_ID:
        # Show all warnings from all groups
        c.execute('''
            SELECT g.group_id, g.group_name, u.user_id, u.first_name, u.last_name, u.username, COUNT(w.id)
            FROM warnings_history w
            JOIN users u ON w.user_id = u.user_id
            JOIN groups g ON w.group_id = g.group_id
            GROUP BY g.group_id, u.user_id
            ORDER BY g.group_id, COUNT(w.id) DESC
        ''')
    else:
        # Check if user is a TARA admin or linked TARA
        # If not in Tara_access, check if linked to any group
        if user_id in admin_ids:
            # global TARA, but not SUPER_ADMIN
            # Show only linked groups
            c.execute('''
                SELECT group_id FROM tara_links WHERE tara_user_id = ?
            ''', (user_id,))
            linked_groups = [row[0] for row in c.fetchall()]
        else:
            # Not SUPER_ADMIN and not global TARA, check if linked TARA
            c.execute('''
                SELECT group_id FROM tara_links WHERE tara_user_id = ?
            ''', (user_id,))
            linked_groups = [row[0] for row in c.fetchall()]

        if not linked_groups:
            conn.close()
            await update.message.reply_text("You have no permission or no linked groups.")
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

    # Organize data by group
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
            full_name = f"{f_name or ''} {l_name or ''}".strip() or "N/A"
            full_name_esc = escape_markdown(full_name, version=2)
            username_esc = f"@{escape_markdown(uname, version=2)}" if uname else "NoUsername"
            msg += (
                f"• *User ID:* `{u_id}`\n"
                f"  *Full Name:* {full_name_esc}\n"
                f"  *Username:* {username_esc}\n"
                f"  *Warnings in this group:* `{w_count}`\n\n"
            )

    try:
        if len(msg) > 4000:
            for i in range(0, len(msg), 4000):
                await update.message.reply_text(msg[i:i+4000], parse_mode='MarkdownV2')
        else:
            await update.message.reply_text(msg, parse_mode='MarkdownV2')
    except Exception as e:
        logger.error(f"Error sending info message: {e}")
        await update.message.reply_text("An error occurred while generating the info report.")

def main():
    init_db()
    TOKEN = os.getenv('BOT_TOKEN')
    if not TOKEN:
        logger.error("BOT_TOKEN is not set.")
        return
    TOKEN = TOKEN.strip()
    if TOKEN.lower().startswith('bot='):
        TOKEN = TOKEN[len('bot='):].strip()

    application = ApplicationBuilder().token(TOKEN).build()

    # Command Handlers (SUPER_ADMIN only except /info)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("set", set_warnings))
    application.add_handler(CommandHandler("tara", add_tara_admin))
    application.add_handler(CommandHandler("rmove", remove_tara_admin))
    application.add_handler(CommandHandler("group_add", group_add))
    application.add_handler(CommandHandler("tara_link", tara_link))
    application.add_handler(CommandHandler("show", show_groups))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("info", info))

    # Message Handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
