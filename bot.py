from telegram.ext import Updater, CommandHandler
from serpapi import GoogleSearch

# Your credentials
TELEGRAM_BOT_TOKEN = '7788581404:AAF2a7p7m8ZGd6tc5DNIj9VJ9saXmTZMJdc'
SERP_API_KEY = 'b5f24ef0644d851c0ee7ce633cebceb464fee210eb80b347b7d39daf107fdbc1'

# Function to fetch jobs
def fetch_jobs():
    params = {
        "engine": "google_jobs",
        "q": "IT jobs",
        "hl": "en",
        "location": "India",
        "api_key": SERP_API_KEY
    }

    search = GoogleSearch(params)
    results = search.get_dict()

    jobs_list = []

    if "jobs_results" in results:
        for job in results["jobs_results"][:5]:
            title = job.get("title", "No Title")
            company = job.get("company_name", "Unknown Company")
            location = job.get("location", "Unknown Location")
            link = job.get("via", "")
            job_info = f"📌 {title}\n🏢 {company}\n📍 {location}\n🔗 {link}\n"
            jobs_list.append(job_info)
    else:
        jobs_list.append("❗ No jobs found.")

    return jobs_list

# /start command handler
def start(update, context):
    update.message.reply_text("🔍 Searching for IT jobs for you... Please wait!")

    jobs = fetch_jobs()

    for job in jobs:
        update.message.reply_text(job)

# Main function
def main():
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))

    print("Bot is running...")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
