import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

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
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome to the Job Search Bot!\nSearching for IT jobs for you...")

    # Automatically search for IT jobs
    query = "IT"
    matched_jobs = [job for job in JOBS if query.lower() in job["title"].lower()]

    if matched_jobs:
        response = "Here are the IT jobs I found:\n\n"
        for job in matched_jobs:
            response += f"🏢 {job['company']}\n📌 {job['title']} - {job['location']}\n\n"
    else:
        response = "Sorry, no IT jobs found right now."

    await update.message.reply_text(response)

# Help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Type any keyword to search for jobs (e.g., 'developer', 'data', 'designer').")

# Manual job search
async def search_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.lower()
    matched_jobs = [job for job in JOBS if query in job["title"].lower()]

    if matched_jobs:
        response = "Here are the jobs I found:\n\n"
        for job in matched_jobs:
            response += f"🏢 {job['company']}\n📌 {job['title']} - {job['location']}\n\n"
    else:
        response = "Sorry, no jobs found matching your search."

    await update.message.reply_text(response)

async def main():
    # Get bot token
    TOKEN = os.getenv("7788581404:AAF2a7p7m8ZGd6tc5DNIj9VJ9saXmTZMJdc")

    if not TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not set")
        return

    # Initialize app
    app = ApplicationBuilder().token(TOKEN).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), search_jobs))

    # Run the bot
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
