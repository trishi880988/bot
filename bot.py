import os
import logging
import shutil
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext
import patoolib

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the folder where files will be extracted
EXTRACT_FOLDER = "extracted_files"

# Command: /start
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "👋 Hello! Send me a ZIP or RAR file, and I will extract it for you."
    )

# Handle ZIP/RAR files
async def handle_file(update: Update, context: CallbackContext):
    user = update.message.from_user
    file = await update.message.document.get_file()

    # Download the file
    file_name = update.message.document.file_name
    await file.download_to_drive(file_name)

    # Check if the file is a ZIP or RAR
    if not (file_name.endswith(".zip") or file_name.endswith(".rar")):
        await update.message.reply_text("❌ Please send a valid ZIP or RAR file.")
        os.remove(file_name)
        return

    # Create extraction folder
    if not os.path.exists(EXTRACT_FOLDER):
        os.makedirs(EXTRACT_FOLDER)

    try:
        # Extract the file
        patoolib.extract_archive(file_name, outdir=EXTRACT_FOLDER)
        await update.message.reply_text("✅ File extracted successfully!")

        # Send extracted files back to the user
        for root, dirs, files in os.walk(EXTRACT_FOLDER):
            for name in files:
                file_path = os.path.join(root, name)
                with open(file_path, "rb") as f:
                    await update.message.reply_document(document=f)

    except Exception as e:
        logger.error(f"Error extracting file: {e}")
        await update.message.reply_text("❌ Failed to extract the file. Please make sure it's a valid ZIP or RAR file.")

    finally:
        # Clean up
        os.remove(file_name)
        shutil.rmtree(EXTRACT_FOLDER, ignore_errors=True)

# Error handler
async def error(update: Update, context: CallbackContext):
    logger.error(f"Update {update} caused error {context.error}")

# Main function
def main():
    # Get the bot token from environment variable
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        raise ValueError("Please set the TELEGRAM_BOT_TOKEN environment variable.")

    # Build the bot application
    application = ApplicationBuilder().token(TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    application.add_error_handler(error)

    # Start the bot
    application.run_polling()

if __name__ == "__main__":
    main()
