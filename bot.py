import os
import logging
import shutil
import time
import asyncio
import libarchive.public
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Define extraction folder
EXTRACT_FOLDER = "extracted_files"
is_extracting = False

# Command: /start
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "👋 Hello! Send me any archive file (ZIP, RAR, 7Z, TAR, etc.), and I'll extract it for you!"
    )

# Command: /cancel
async def cancel(update: Update, context: CallbackContext):
    global is_extracting
    if is_extracting:
        is_extracting = False
        await update.message.reply_text("🛑 Extraction process cancelled.")
    else:
        await update.message.reply_text("❌ No extraction is currently running.")

# Function to extract files using libarchive
async def extract_files(file_path, output_folder):
    global is_extracting
    is_extracting = True
    os.makedirs(output_folder, exist_ok=True)
    
    try:
        with libarchive.public.file_reader(file_path) as archive:
            for entry in archive:
                if not is_extracting:
                    return  # Cancel if the user requests
                
                entry_path = os.path.join(output_folder, entry.pathname)
                os.makedirs(os.path.dirname(entry_path), exist_ok=True)
                with open(entry_path, 'wb') as f:
                    for block in entry.get_blocks():
                        f.write(block)
    except Exception as e:
        logger.error(f"Error extracting file: {e}")
        return False
    
    is_extracting = False
    return True

# Function to split large files into chunks (50MB each)
def split_file(file_path, chunk_size=50 * 1024 * 1024):
    chunks = []
    with open(file_path, "rb") as f:
        chunk_num = 1
        while chunk := f.read(chunk_size):
            chunk_name = f"{file_path}.part{chunk_num}"
            with open(chunk_name, "wb") as chunk_file:
                chunk_file.write(chunk)
            chunks.append(chunk_name)
            chunk_num += 1
    return chunks

# Handle archive files
async def handle_file(update: Update, context: CallbackContext):
    global is_extracting
    user = update.message.from_user
    file = await update.message.document.get_file()
    file_name = update.message.document.file_name
    file_size = update.message.document.file_size / (1024 * 1024 * 1024)  # Convert to GB
    
    await update.message.reply_text(f"📂 File received: {file_name} ({file_size:.2f} GB)")
    await file.download_to_drive(file_name)
    await update.message.reply_text("⏳ Extracting your file... Please wait.")
    
    # Extract the file asynchronously
    success = await extract_files(file_name, EXTRACT_FOLDER)
    
    if not success:
        await update.message.reply_text("❌ Failed to extract the archive. It might be corrupted.")
        os.remove(file_name)
        return
    
    extracted_files = []
    for root, dirs, files in os.walk(EXTRACT_FOLDER):
        for name in files:
            extracted_files.append(os.path.join(root, name))
    
    if not extracted_files:
        await update.message.reply_text("❌ No files found in the archive.")
    else:
        for file_path in extracted_files:
            file_size = os.path.getsize(file_path) / (1024 * 1024 * 1024)
            if file_size > 2:
                await update.message.reply_text(f"📦 Splitting large file: {os.path.basename(file_path)} ({file_size:.2f} GB)")
                chunks = split_file(file_path)
                for chunk in chunks:
                    with open(chunk, "rb") as f:
                        await update.message.reply_document(document=f)
                    os.remove(chunk)
            else:
                with open(file_path, "rb") as f:
                    await update.message.reply_document(document=f)
    
    os.remove(file_name)
    shutil.rmtree(EXTRACT_FOLDER, ignore_errors=True)

# Error handler
async def error(update: Update, context: CallbackContext):
    logger.error(f"Update {update} caused error {context.error}")

# Main function
def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        raise ValueError("Please set the TELEGRAM_BOT_TOKEN environment variable.")
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    application.add_error_handler(error)
    
    application.run_polling()

if __name__ == "__main__":
    main()
