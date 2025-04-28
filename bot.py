import os
import requests
from bs4 import BeautifulSoup
from telegram import Bot
from telegram.ext import ApplicationBuilder, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio

# Set your environment variables in Railway (TELEGRAM_BOT_TOKEN and CHAT_ID)
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")  # Should be a string

sent_jobs = set()

# Scrape jobs from RemoteOK
async def scrape_remoteok():
    url = "https://remoteok.com/remote-it-jobs"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    jobs = []
    for tr in soup.find_all('tr', class_='job'):
        a_tag = tr.find('a', itemprop='url')
        if a_tag:
            link = "https://remoteok.com" + a_tag['href']
            title_tag = tr.find('h2', itemprop='title')
            if title_tag:
                job_title = title_tag.get_text(strip=True)
                jobs.append((job_title, link))
    return jobs

# Scrape jobs from Wellfound
async def scrape_wellfound():
    url = "https://wellfound.com/jobs"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    jobs = []
    for div in soup.find_all('div', class_='styles_component__1AIbG'):
        title_tag = div.find('a')
        if title_tag:
            link = "https://wellfound.com" + title_tag['href']
            job_title = title_tag.get_text(strip=True)
            jobs.append((job_title, link))
    return jobs

# Scrape jobs from WeWorkRemotely
async def scrape_weworkremotely():
    url = "https://weworkremotely.com/categories/remote-programming-jobs"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    jobs = []
    for li in soup.find_all('li', class_='feature'):
        a_tag = li.find('a')
        if a_tag:
            link = "https://weworkremotely.com" + a_tag['href']
            title_tag = li.find('span', class_='title')
            if title_tag:
                job_title = title_tag.get_text(strip=True)
                jobs.append((job_title, link))
    return jobs

# Function to send new jobs to Telegram
async def send_new_jobs(bot: Bot):
    all_jobs = []
    all_jobs += await scrape_remoteok()
    all_jobs += await scrape_wellfound()
    all_jobs += await scrape_weworkremotely()

    for job_title, link in all_jobs:
        unique_id = f"{job_title}_{link}"
        if unique_id not in sent_jobs:
            sent_jobs.add(unique_id)
            message = f"💼 [{job_title}]({link})"
            try:
                await bot.send_message(
                    chat_id=CHAT_ID,
                    text=message,
                    parse_mode='Markdown',
                    disable_web_page_preview=False
                )
            except Exception as e:
                print(f"Error sending job: {e}")

# Background scheduler task
async def scheduled_task(app):
    await send_new_jobs(app.bot)

# Main
async def main():
    print("Bot is starting...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Start job fetching scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(scheduled_task, "interval", minutes=2, args=[app])
    scheduler.start()
    print("Scheduler started...")

    print("Bot started and polling...")
    # Start the bot and polling
    await app.run_polling()

# Entry point for the script
if __name__ == "__main__":
    # Instead of asyncio.run(), directly start the event loop
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except RuntimeError as e:
        print(f"Error: {e}")
        print("It seems an event loop is already running.")
