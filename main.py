import os
import logging
from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, CallbackContext
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
API_TOKEN = os.getenv('TELEGRAM_API_TOKEN')

# Initialize logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Define the authorized user ID
AUTHORIZED_USER_ID = 6177929931

def start(update: Update, context: CallbackContext):
    """Handler for the /start command."""
    update.message.reply_text("Hello! I'm your admin bot. Use /ban <user_id> to ban a user.")

def ban_user(update: Update, context: CallbackContext):
    """Handler for the /ban command."""
    # Check if the command issuer is authorized
    user_id = update.effective_user.id
    if user_id != AUTHORIZED_USER_ID:
        update.message.reply_text("You are not authorized to use this command.")
        logger.warning(f"Unauthorized access attempt by user ID: {user_id}")
        return

    # Ensure a user ID is provided
    if len(context.args) != 1:
        update.message.reply_text("Usage: /ban <user_id>")
        return

    try:
        # Parse the target user ID
        target_user_id = int(context.args[0])

        # Attempt to ban the user
        chat_id = update.effective_chat.id
        context.bot.kick_chat_member(chat_id=chat_id, user_id=target_user_id)

        # Send confirmation in the chat
        update.message.reply_text(f"User {target_user_id} has been banned.")

        # Send a message to the banned user
        context.bot.send_message(
            chat_id=target_user_id,
            text="You got ban from bot."
        )

        logger.info(f"User {target_user_id} has been banned by admin {user_id}.")

    except ValueError:
        update.message.reply_text("Invalid user ID. Please provide a numerical user ID.")
    except Exception as e:
        update.message.reply_text(f"An error occurred: {e}")
        logger.error(f"Error banning user: {e}")

def main():
    """Main function to start the bot."""
    # Initialize the bot and dispatcher
    updater = Updater(token=API_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Add command handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("ban", ban_user, pass_args=True))

    # Start polling for updates
    updater.start_polling()
    logger.info("Bot started and is polling for updates...")

    # Run the bot until you press Ctrl-C or the process receives SIGINT, SIGTERM, or SIGABRT
    updater.idle()

if __name__ == '__main__':
    main()
