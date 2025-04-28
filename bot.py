import os
import logging
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Telegram token and webhook
TOKEN = os.environ["TELEGRAM_TOKEN"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]  # e.g., https://yourproject.up.railway.app

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Scraper
def scrape_indeed_jobs(query="IT", location="Remote", num_results=5):
    headers = {"User-Agent": "Mozilla/5.0"}
    search_query = '+'.join(query.split())
    search_location = '+'.join(location.split())
    url = f"https://www.indeed.com/jobs?q={search_query}&l={search_location}"

    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, "html.parser")
    cards = soup.find_all("a", class_="tapItem")

    jobs = []
    for card in cards[:num_results]:
        title = card.find("h2", class_="jobTitle").text.strip()
        company = card.find("span", class_="companyName").text.strip()
        location_tag = card.find("div", class_="companyLocation")
        location = location_tag.text.strip() if location_tag else "N/A"
        link = "https://www.indeed.com" + card["href"]
        jobs.append({"title": title, "company": company, "location": location, "url": link})
    return jobs

# Bot command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📡 Fetching latest IT jobs...")
    jobs = scrape_indeed_jobs()
    for job in jobs:
        message = (
            f"*{job['title']}*\n"
            f"🏢 {job['company']}\n"
            f"📍 {job['location']}\n"
            f"🔗 [Apply Here]({job['url']})"
        )
        await update.message.reply_text(message, parse_mode="Markdown", disable_web_page_preview=True)

# FastAPI setup
app = FastAPI()

@app.on_event("startup")
async def startup():
    global bot_app
    bot_app = Application.builder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    await bot_app.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")

@app.post("/webhook")
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, bot_app.bot)
    await bot_app.process_update(update)
    return {"ok": True}
