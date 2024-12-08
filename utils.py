# utils.py

import sqlite3

DATABASE = 'warnings.db'

def add_global_tara(tara_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO global_taras (tara_id) VALUES (?)', (tara_id,))
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError("Global TARA already exists.")
    finally:
        conn.close()

def remove_global_tara(tara_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('DELETE FROM global_taras WHERE tara_id = ?', (tara_id,))
    conn.commit()
    conn.close()

def is_global_tara(user_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT 1 FROM global_taras WHERE tara_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return bool(result)

def add_normal_tara(tara_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO normal_taras (tara_id) VALUES (?)', (tara_id,))
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError("Normal TARA already exists.")
    finally:
        conn.close()

def remove_normal_tara(tara_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('DELETE FROM normal_taras WHERE tara_id = ?', (tara_id,))
    conn.commit()
    conn.close()

def is_normal_tara(user_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT 1 FROM normal_taras WHERE tara_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return bool(result)

def add_group(group_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO groups (group_id) VALUES (?)', (group_id,))
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError("Group already exists.")
    finally:
        conn.close()

def remove_group(group_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('DELETE FROM groups WHERE group_id = ?', (group_id,))
    conn.commit()
    conn.close()

def set_group_name(group_id, group_name):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('UPDATE groups SET group_name = ? WHERE group_id = ?', (group_name, group_id))
    conn.commit()
    conn.close()

def group_exists(group_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT 1 FROM groups WHERE group_id = ?', (group_id,))
    result = c.fetchone()
    conn.close()
    return bool(result)

def link_tara_to_group(tara_id, group_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    # Check if TARA exists
    c.execute('SELECT 1 FROM global_taras WHERE tara_id = ?', (tara_id,))
    if not c.fetchone():
        c.execute('SELECT 1 FROM normal_taras WHERE tara_id = ?', (tara_id,))
        if not c.fetchone():
            conn.close()
            raise ValueError("TARA ID does not exist.")
    # Check if group exists
    if not group_exists(group_id):
        conn.close()
        raise ValueError("Group ID does not exist.")
    # Check if link already exists
    c.execute('SELECT 1 FROM tara_links WHERE tara_user_id = ? AND group_id = ?', (tara_id, group_id))
    if c.fetchone():
        conn.close()
        raise ValueError("TARA is already linked to this group.")
    # Link
    c.execute('INSERT INTO tara_links (tara_user_id, group_id) VALUES (?, ?)', (tara_id, group_id))
    conn.commit()
    conn.close()

def unlink_tara_from_group(tara_id, group_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('DELETE FROM tara_links WHERE tara_user_id = ? AND group_id = ?', (tara_id, group_id))
    conn.commit()
    conn.close()

def add_bypass_user(user_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO bypass_users (user_id) VALUES (?)', (user_id,))
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError("User is already bypassed.")
    finally:
        conn.close()

def remove_bypass_user(user_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('DELETE FROM bypass_users WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def get_all_groups_and_links():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        SELECT g.group_id, g.group_name, t.tara_user_id
        FROM groups g
        LEFT JOIN tara_links t ON g.group_id = t.group_id
    ''')
    rows = c.fetchall()
    conn.close()
    groups = {}
    for row in rows:
        group_id, group_name, tara_id = row
        if group_id not in groups:
            groups[group_id] = {
                'group_id': group_id,
                'group_name': group_name,
                'taras': []
            }
        if tara_id:
            groups[group_id]['taras'].append(tara_id)
    return list(groups.values())

def get_warnings_info(user_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        SELECT warning_number, timestamp, group_id
        FROM warnings_history
        WHERE user_id = ?
        ORDER BY timestamp DESC
    ''', (user_id,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        return []
    return [{'warning_number': row[0], 'timestamp': row[1], 'group_id': row[2]} for row in rows]

def test_arabic_detection(text):
    # Placeholder implementation
    # You should replace this with actual Arabic detection logic
    arabic_chars = set('ءآأؤإئابةتثجحخدذرزسشصضطظعغفقكلمنهوي')
    detected = any(char in arabic_chars for char in text)
    return "Arabic text detected." if detected else "No Arabic text detected."

def get_comprehensive_overview():
    """
    Returns a comprehensive overview of groups, members, TARAs, and bypassed users.
    """
    try:
        overview = {}
        # Groups and Members
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT group_id, group_name FROM groups')
        groups = c.fetchall()
        overview['groups'] = []
        for group in groups:
            group_id, group_name = group
            # Fetch members - assuming you have a table or method to get group members
            # Placeholder: Empty list
            members = []  # Replace with actual member retrieval logic
            overview['groups'].append({
                'group_id': group_id,
                'group_name': group_name,
                'members': members
            })
        # TARAs
        c.execute('SELECT tara_id FROM global_taras')
        global_taras = c.fetchall()
        c.execute('SELECT tara_id FROM normal_taras')
        normal_taras = c.fetchall()
        taras = []
        for tara in global_taras:
            taras.append({
                'tara_id': tara[0],
                'is_global': True,
                'linked_groups': []  # Replace with actual linked groups retrieval
            })
        for tara in normal_taras:
            taras.append({
                'tara_id': tara[0],
                'is_global': False,
                'linked_groups': []  # Replace with actual linked groups retrieval
            })
        overview['taras'] = taras
        # Bypassed Users
        c.execute('SELECT user_id FROM bypass_users')
        bypassed_users = c.fetchall()
        overview['bypassed_users'] = [user[0] for user in bypassed_users]
        conn.close()
        return overview
    except Exception as e:
        logger.error(f"Error generating comprehensive overview: {e}")
        return None

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
