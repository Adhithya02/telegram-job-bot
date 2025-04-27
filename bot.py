from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from serpapi import GoogleSearch
import os

# Your credentials here
TELEGRAM_BOT_TOKEN = '7788581404:AAF2a7p7m8ZGd6tc5DNIj9VJ9saXmTZMJdc'
SERP_API_KEY = '7788581404:AAF2a7p7m8ZGd6tc5DNIj9VJ9saXmTZMJdc'

# Function to fetch jobs using SerpAPI
def fetch_jobs():
    params = {
        "engine": "google_jobs",
        "q": "IT jobs",
        "hl": "en",
        "location": "India",  # Change location if you want
        "api_key": SERP_API_KEY
    }

    search = GoogleSearch(params)
    results = search.get_dict()

    jobs_list = []

    if "jobs_results" in results:
        for job in results["jobs_results"][:5]:  # Limit to 5 jobs
            title = job.get("title", "No Title")
            company = job.get("company_name", "Unknown Company")
            location = job.get("location", "Unknown Location")
            link = job.get("via", "")
            job_info = f"📌 *{title}*\n🏢 {company}\n📍 {location}\n🔗 {link}\n"
            jobs_list.append(job_info)
    else:
        jobs_list.append("❗ No jobs found at the moment.")

    return jobs_list

# Handler for /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Searching for IT jobs for you... Please wait!")

    jobs = fetch_jobs()

    for job in jobs:
        await update.message.reply_markdown(job)

# Main function to run the bot
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    print("Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
