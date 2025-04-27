import os
from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# Hardcoded job list (you can expand this)
JOBS = [
    {"title": "Software Engineer", "location": "Remote", "company": "TechCorp"},
    {"title": "Data Scientist", "location": "New York", "company": "DataWorld"},
    {"title": "Web Developer", "location": "Remote", "company": "Webify"},
    {"title": "UI/UX Designer", "location": "San Francisco", "company": "DesignPro"},
]

# Start command
def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Welcome to the Job Search Bot!\n"
        "Type a job title to search (example: 'developer', 'data', 'designer')."
    )

# Help command
def help_command(update: Update, context: CallbackContext):
    update.message.reply_text("Just type a keyword, and I'll find jobs for you!")

# Job search handler
def search_jobs(update: Update, context: CallbackContext):
    query = update.message.text.lower()
    matched_jobs = [job for job in JOBS if query in job["title"].lower()]

    if matched_jobs:
        response = "Here are the jobs I found:\n\n"
        for job in matched_jobs:
            response += f"🏢 {job['company']}\n📌 {job['title']} - {job['location']}\n\n"
    else:
        response = "Sorry, no jobs found matching your search."

    update.message.reply_text(response)

def main():
    # Get token from environment variable
    TOKEN = os.getenv("7788581404:AAF2a7p7m8ZGd6tc5DNIj9VJ9saXmTZMJdc")

    if not TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not set")
        return

    # Initialize bot
    updater = Updater(TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Register handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, search_jobs))

    # Start the bot
    PORT = int(os.environ.get('PORT', 8443))
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
