import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# === YOUR TOKENS ===
BOT_TOKEN = '7788581404:AAF2a7p7m8ZGd6tc5DNIj9VJ9saXmTZMJdc'
SERP_API_KEY = 'b5f24ef0644d851c0ee7ce633cebceb464fee210eb80b347b7d39daf107fdbc1'

# === Setup logging ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# === Function to search jobs ===
def search_jobs(query="Software Developer", location="Remote"):
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_jobs",
        "q": query,
        "location": location,
        "api_key": SERP_API_KEY
    }
    response = requests.get(url, params=params)
    data = response.json()
    
    job_listings = data.get('jobs_results', [])
    results = []
    for job in job_listings[:5]:  # Limit to first 5 results
        title = job.get('title', 'No Title')
        company = job.get('company_name', 'No Company')
        link = job.get('related_links', [{}])[0].get('link', 'No Link')
        results.append(f"📌 *{title}* at *{company}*\n🔗 [Apply Here]({link})")
    return results if results else ["No jobs found!"]

# === Telegram command handler ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Searching for jobs... Please wait!")

    jobs = search_jobs()

    for job in jobs:
        await update.message.reply_markdown(job)

# === Main ===
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler('start', start))

    print("Bot is running...")
    app.run_polling()
