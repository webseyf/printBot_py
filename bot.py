import logging
import json
import os
from telegram import Update, InputFile, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler
from telegram.ext import CallbackQueryHandler
from telegram.ext import PicklePersistence
from telegram.ext import CallbackQueryHandler
from telegram.ext import Application

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Define constants
API_TOKEN = '7925976029:AAGsNZoLSbuhaqQRHmo5cdRA1p-s2TSDq98'  
ADMIN_ID = 1090330124  

# Define states for the conversation handler
FILE, PHONE, PRINT_TYPE, DESCRIPTION = range(4)

# Path to save files
PENDING_DIR = 'received_files/pending/'
CONFIRMED_DIR = 'received_files/confirmed/'
REJECTED_DIR = 'received_files/rejected/'

# Ensure the directories exist
os.makedirs(PENDING_DIR, exist_ok=True)
os.makedirs(CONFIRMED_DIR, exist_ok=True)
os.makedirs(REJECTED_DIR, exist_ok=True)

# File to store submission data
JSON_FILE = 'submissions.json'

# Load existing submissions from the JSON file if it exists
def load_submissions():
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, 'r') as file:
            return json.load(file)
    return {}

submissions = load_submissions()

# Save submissions to the JSON file
def save_submissions():
    with open(JSON_FILE, 'w') as file:
        json.dump(submissions, file, indent=4)

# Start command
async def start(update: Update, context: CallbackContext) -> int:
    # Inform the user to send a file
    await update.message.reply_text("Welcome to the printing service bot! Please send me a file you'd like to print.")
    return FILE

# Handle file uploads
async def handle_file(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    file = update.message.document

    # Save the file to the pending directory
    file_path = os.path.join(PENDING_DIR, file.file_name)
    await file.download_to_drive(file_path)
    
    # Store file information in the JSON structure
    submissions[user_id] = {
        'file_name': file.file_name,
        'file_path': file_path,
        'phone_number': None,
        'print_type': None,
        'description': None,
        'status': 'pending'
    }

    save_submissions()

    # Ask for the user's phone number
    keyboard = [[KeyboardButton("Share Phone Number", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Please share your phone number.", reply_markup=reply_markup)
    return PHONE

# Handle phone number input
async def handle_phone(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    phone = update.message.contact.phone_number

    # Store the phone number in the submission data
    if user_id in submissions:
        submissions[user_id]['phone_number'] = phone
        save_submissions()

    # Ask for print type
    await update.message.reply_text("Would you like color or black & white printing? Reply with 'color' or 'bw'.")
    return PRINT_TYPE

# Handle print type input
async def handle_print_type(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    print_type = update.message.text.lower()

    # Validate and store print type
    if print_type not in ['color', 'bw']:
        await update.message.reply_text("Please choose between 'color' or 'bw' printing.")
        return PRINT_TYPE

    submissions[user_id]['print_type'] = print_type
    save_submissions()

    # Ask for description
    await update.message.reply_text("Please provide a description or any special instructions (optional).")
    return DESCRIPTION

# Handle description input
async def handle_description(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    description = update.message.text

    # Store description in submission
    submissions[user_id]['description'] = description
    save_submissions()

    # Confirm submission
    await update.message.reply_text("Your submission has been recorded! The admin will review it shortly.")
    return ConversationHandler.END

# Admin commands
async def admin(update: Update, context: CallbackContext) -> None:
    if update.message.from_user.id != ADMIN_ID:
        # Notify unauthorized users
        await update.message.reply_text("You are not authorized to use this command.")
        return

    # Check for pending submissions
    pending_submissions = [f"{user_id}: {data['file_name']}" for user_id, data in submissions.items() if data['status'] == 'pending']
    if not pending_submissions:
        await update.message.reply_text("No pending submissions.")
    else:
        await update.message.reply_text("Pending submissions:\n" + "\n".join(pending_submissions))

async def approve(update: Update, context: CallbackContext) -> None:
    if update.message.from_user.id != ADMIN_ID:
        # Notify unauthorized users
        await update.message.reply_text("You are not authorized to use this command.")
        return

    user_id = int(context.args[0])
    if user_id not in submissions or submissions[user_id]['status'] != 'pending':
        # Handle invalid or already processed submissions
        await update.message.reply_text("Invalid submission ID or already processed.")
        return

    # Move file to 'confirmed' folder
    submission = submissions[user_id]
    confirmed_path = os.path.join(CONFIRMED_DIR, submission['file_name'])
    os.rename(submission['file_path'], confirmed_path)
    submission['status'] = 'approved'
    submission['file_path'] = confirmed_path
    save_submissions()

    # Notify user of approval
    await context.bot.send_message(user_id, f"Your submission '{submission['file_name']}' has been approved!")
    await update.message.reply_text(f"Submission {user_id} has been approved.")

async def reject(update: Update, context: CallbackContext) -> None:
    if update.message.from_user.id != ADMIN_ID:
        # Notify unauthorized users
        await update.message.reply_text("You are not authorized to use this command.")
        return

    user_id = int(context.args[0])
    if user_id not in submissions or submissions[user_id]['status'] != 'pending':
        # Handle invalid or already processed submissions
        await update.message.reply_text("Invalid submission ID or already processed.")
        return

    # Move file to 'rejected' folder
    submission = submissions[user_id]
    rejected_path = os.path.join(REJECTED_DIR, submission['file_name'])
    os.rename(submission['file_path'], rejected_path)
    submission['status'] = 'rejected'
    submission['file_path'] = rejected_path
    save_submissions()

    # Notify user of rejection
    await context.bot.send_message(user_id, f"Your submission '{submission['file_name']}' has been rejected.")
    await update.message.reply_text(f"Submission {user_id} has been rejected.")

async def main() -> None:
    persistence = PicklePersistence('bot_data')

    # Create application instance
    application = Application.builder().token(API_TOKEN).persistence(persistence).build()

    # Define conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            FILE: [MessageHandler(filters.Document, handle_file)],
            PHONE: [MessageHandler(filters.Contact, handle_phone)],  # Corrected filter here
            PRINT_TYPE: [MessageHandler(filters.Text & ~filters.Command, handle_print_type)],
            DESCRIPTION: [MessageHandler(filters.Text & ~filters.Command, handle_description)]
        },
        fallbacks=[]
    )

    # Add conversation handler to dispatcher
    application.add_handler(conv_handler)

    # Add admin commands
    application.add_handler(CommandHandler('admin', admin))
    application.add_handler(CommandHandler('approve', approve, pass_args=True))
    application.add_handler(CommandHandler('reject', reject, pass_args=True))

    # Start the Bot
    await application.run_polling()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
