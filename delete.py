# delete.py

from telegram.ext import CommandHandler, ContextTypes
from telegram import Update

async def be_sad_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Your implementation to enable message deletion in a group
    pass

async def be_happy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Your implementation to disable message deletion in a group
    pass

# Define handlers
be_sad_handler = CommandHandler("be_sad", be_sad_cmd)
be_happy_handler = CommandHandler("be_happy", be_happy_cmd)
