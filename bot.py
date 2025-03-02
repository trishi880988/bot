import os
import logging
import shutil
import time
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext
import patoolib

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the folder where files will be extracted
EXTRACT_FOLDER = "extracted_files"

# Global flag to track extraction process
is_extracting = False

# Command: /start
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "👋 Hello! Send me a ZIP or RAR file, and I will extract it for you."
    )

# Command: /cancel
async def cancel(update: Update, context: CallbackContext):
    global is_extracting
    if is_extracting:
        is_extracting = False
        await update.message.reply_text("🛑 Extraction process cancelled.")
    else:
        await update.message.reply_text("❌ No extraction process is currently running.")

# Handle ZIP/RAR files
async def handle_file(update: Update, context: CallbackContext):
    global is_extracting
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
        # Notify user that extraction is starting
        start_time = time.time()
        is_extracting = True
        await update.message.reply_text(
            "⏳ Extracting your file... Please wait.\n"
            "🛑 Use /cancel to stop the extraction."
        )

        # Extract the file
        patoolib.extract_archive(file_name, outdir=EXTRACT_FOLDER)
        extraction_time = time.time() - start_time

        # Check if extraction was cancelled
        if not is_extracting:
            await update.message.reply_text("🛑 Extraction process was cancelled.")
            return

        # Notify user about extraction speed
        await update.message.reply_text(f"✅ File extracted successfully in {extraction_time:.2f} seconds!")

        # Send extracted files back to the user
        extracted_files = []
        for root, dirs, files in os.walk(EXTRACT_FOLDER):
            for name in files:
                file_path = os.path.join(root, name)
                extracted_files.append(file_path)

        if not extracted_files:
            await update.message.reply_text("❌ No files found in the archive.")
        else:
            for file_path in extracted_files:
                with open(file_path, "rb") as f:
                    await update.message.reply_document(document=f)

    except patoolib.util.PatoolError as e:
        logger.error(f"Error extracting file: {e}")
        await update.message.reply_text("❌ Failed to extract the file. Please make sure it's a valid ZIP or RAR file.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await update.message.reply_text("❌ An unexpected error occurred. Please try again.")

    finally:
        # Clean up
        is_extracting = False
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
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    application.add_error_handler(error)

    # Start the bot
    application.run_polling()

if __name__ == "__main__":
    main()
