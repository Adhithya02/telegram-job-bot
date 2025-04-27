import os
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# Hardcoded job list
JOBS = [
    {"title": "Software Engineer", "location": "Remote", "company": "TechCorp"},
    {"title": "IT Support Specialist", "location": "New York", "company": "NetSolutions"},
    {"title": "Data Scientist", "location": "Remote", "company": "DataWorld"},
    {"title": "Web Developer", "location": "Remote", "company": "Webify"},
    {"title": "UI/UX Designer", "location": "San Francisco", "company": "DesignPro"},
    {"title": "IT Manager", "location": "Chicago", "company": "SysAdmin Inc."},
]

# Start command
def start(update: Update, context: CallbackContext):
    update.message.reply_text("Welcome to the Job Search Bot!\nSearching for IT jobs for you...")

    # Automatically search for IT jobs
    query = "IT"
    matched_jobs = [job for job in JOBS if query.lower() in job["title"].lower()]

    if matched_jobs:
        response = "Here are the IT jobs I found:\n\n"
        for job in matched_jobs:
            response += f"🏢 {job['company']}\n📌 {job['title']} - {job['location']}\n\n"
    else:
        response = "Sorry, no IT jobs found right now."

    update.message.reply_text(response)

# Help command
def help_command(update: Update, context: CallbackContext):
    update.message.reply_text("Type any keyword to search for jobs (e.g., 'developer', 'data', 'designer').")

# Manual job search
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
    # Get bot token from environment variable
    TOKEN = os.getenv("7788581404:AAF2a7p7m8ZGd6tc5DNIj9VJ9saXmTZMJdc")

    if not TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not set")
        return

    # Create updater and dispatcher
    updater = Updater(TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, search_jobs))

    # Start polling
    PORT = int(os.environ.get('PORT', 8443))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
