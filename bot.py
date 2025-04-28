from telegram.ext import ApplicationBuilder, CommandHandler
from telegram import Update
import logging
import os
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI
from telegram.ext import Application
from telegram.ext.webhook import WebhookServer

TOKEN = os.environ.get("TELEGRAM_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # Add this in Railway too!

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Scraping function
def scrape_indeed_jobs(query="IT", location="Remote", num_results=5):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    search_query = '+'.join(query.split())
    search_location = '+'.join(location.split())
    url = f"https://www.indeed.com/jobs?q={search_query}&l={search_location}"

    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, 'html.parser')
    cards = soup.find_all('a', class_='tapItem')

    jobs = []
    for card in cards[:num_results]:
        title = card.find('h2', class_='jobTitle').text.strip()
        company = card.find('span', class_='companyName').text.strip()
        location_tag = card.find('div', class_='companyLocation')
        location = location_tag.text.strip() if location_tag else "N/A"
        link = "https://www.indeed.com" + card['href']
        jobs.append({
            "title": title,
            "company": company,
            "location": location,
            "url": link
        })
    return jobs

# Bot command
async def start(update: Update, context):
    await update.message.reply_text("Welcome! Fetching latest IT jobs...")
    jobs = scrape_indeed_jobs()
    if jobs:
        for job in jobs:
            text = (
                f"🔹 *{job['title']}*\n"
                f"🏢 {job['company']}\n"
                f"📍 {job['location']}\n"
                f"🔗 [Apply Here]({job['url']})"
            )
            await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)

# Start application with webhook
@app.on_event("startup")
async def startup():
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))

    # Set Telegram webhook
    await application.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")

    # Start webhook server
    webhook_server = WebhookServer(application=application, path="/webhook", app=app)
    await webhook_server.run()

