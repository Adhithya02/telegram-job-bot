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

# === Async Function to search jobs ===
async def search_jobs(location="India"):
    url = "https://serpapi.com/search.json"
    queries = [
        "Software Developer",
        "Python Developer",
        "Web Developer",
        "Backend Developer",
        "Frontend Developer",
        "Data Scientist",
        "Machine Learning Engineer",
        "DevOps Engineer",
        "Full Stack Developer",
        "Mobile App Developer"
    ]

    all_jobs = []

    try:
        for query in queries:
            params = {
                "engine": "google_jobs",
                "q": query,
                "location": location,
                "api_key": SERP_API_KEY
            }

            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            if "error" in data:
                print(f"Error fetching {query}: {data['error']}")
                continue

            job_listings = data.get('jobs_results', [])

            for job in job_listings[:2]:  # Fetch 2 jobs per query (so 10x2=20 jobs total)
                title = job.get('title', 'No Title')
                company = job.get('company_name', 'No Company')

                apply_link = (
                    job.get('apply_options', [{}])[0].get('link') or
                    job.get('detected_extensions', {}).get('apply_link') or
                    job.get('related_links', [{}])[0].get('link', 'Link not available')
                )

                message = f"📌 *{title}* at *{company}*\n🔗 [Apply Here]({apply_link})"
                all_jobs.append(message)

        return all_jobs if all_jobs else ["No IT jobs found!"]

    except Exception as e:
        return [f"Error fetching jobs: {e}"]



# === /start command handler ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Searching for jobs... Please wait!")

    jobs = await search_jobs()  # Await the search_jobs call

    for job in jobs:
        await update.message.reply_markdown(job)

# === Main ===
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler('start', start))

    print("🤖 Bot is running...")
    app.run_polling()
