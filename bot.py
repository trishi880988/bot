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
        "👋 Hello! Send me a ZIP or RAR file, and I will extract it for you.\n"
        "📦 I can handle large files (GBs) and send them in chunks."
    )

# Command: /cancel
async def cancel(update: Update, context: CallbackContext):
    global is_extracting
    if is_extracting:
        is_extracting = False
        await update.message.reply_text("🛑 Extraction process cancelled.")
    else:
        await update.message.reply_text("❌ No extraction process is currently running.")

# Function to split large files into chunks
def split_file(file_path, chunk_size=50 * 1024 * 1024):  # 50 MB chunks
    chunk_number = 1
    chunks = []
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            chunk_name = f"{file_path}.part{chunk_number}"
            with open(chunk_name, "wb") as chunk_file:
                chunk_file.write(chunk)
            chunks.append(chunk_name)
            chunk_number += 1
    return chunks

# Function to extract files (run in a separate thread)
def extract_files(file_name, extract_folder):
    patoolib.extract_archive(file_name, outdir=extract_folder)

# Handle ZIP/RAR files
async def handle_file(update: Update, context: CallbackContext):
    global is_extracting
    user = update.message.from_user
    file = await update.message.document.get_file()

    # File details
    file_name = update.message.document.file_name
    file_size = update.message.document.file_size / (1024 * 1024 * 1024)  # Size in GB

    # Notify user about file size
    await update.message.reply_text(f"📄 File received: {file_name} ({file_size:.2f} GB)")

    # Download the file
    start_time = time.time()
    await file.download_to_drive(file_name)
    download_time = time.time() - start_time

    # Calculate download speed
    download_speed = (file_size * 1024) / download_time  # Speed in MB/s
    await update.message.reply_text(f"📥 Downloaded {file_name} ({file_size:.2f} GB) at {download_speed:.2f} MB/s.")

    # Check if the file is a ZIP or RAR (case-insensitive and allows numbers)
    allowed_extensions = [".zip", ".rar"]
    if not any(file_name.lower().endswith(ext) for ext in allowed_extensions):
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

        # Extract the file in a separate thread (to avoid blocking)
        await asyncio.to_thread(extract_files, file_name, EXTRACT_FOLDER)
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
                file_size = os.path.getsize(file_path) / (1024 * 1024 * 1024)  # Size in GB
                if file_size > 2:  # If file is larger than 2 GB, split it into chunks
                    await update.message.reply_text(f"📦 Splitting large file: {os.path.basename(file_path)} ({file_size:.2f} GB)")
                    chunks = split_file(file_path)
                    for chunk in chunks:
                        with open(chunk, "rb") as f:
                            await update.message.reply_document(document=f)
                        os.remove(chunk)
                else:
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
