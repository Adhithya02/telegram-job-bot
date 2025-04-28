import os
import requests
from bs4 import BeautifulSoup
from telegram import Bot
from telegram.ext import ApplicationBuilder
from apscheduler.schedulers.background import BackgroundScheduler
import asyncio
import nest_asyncio

nest_asyncio.apply()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

sent_jobs = set()

# SCRAPERS:

def scrape_remoteok():
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

def scrape_wellfound():
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

def scrape_weworkremotely():
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

async def send_new_jobs():
    bot = Bot(BOT_TOKEN)
    all_jobs = scrape_remoteok() + scrape_wellfound() + scrape_weworkremotely()

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

def start_scheduler(loop):
    scheduler = BackgroundScheduler()

    def sync_send_jobs():
        asyncio.run_coroutine_threadsafe(send_new_jobs(), loop)

    scheduler.add_job(sync_send_jobs, 'interval', minutes=2)
    scheduler.start()
    print("Scheduler started...")

async def main():
    global CHAT_ID
    bot = Bot(BOT_TOKEN)

    if not CHAT_ID:
        updates = await bot.get_updates()
        if updates:
            CHAT_ID = updates[-1].message.chat_id
            print(f"Detected CHAT_ID automatically: {CHAT_ID}")

    loop = asyncio.get_running_loop()
    start_scheduler(loop)

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    print("Bot started and polling...")
    await app.run_polling()

if __name__ == "__main__":
    print("Bot is starting...")
    asyncio.get_event_loop().run_until_complete(main())
