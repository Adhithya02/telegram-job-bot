import os
import requests
from bs4 import BeautifulSoup
from telegram import Bot
from telegram.ext import ApplicationBuilder
from apscheduler.schedulers.background import BackgroundScheduler
import asyncio

# Load environment variables
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")  # Can be empty at start

# Websites to scrape
JOB_SITES = [
    "https://www.indeed.com/q-IT-jobs.html",
    "https://www.monster.com/jobs/search/?q=IT&where=",
    "https://remoteok.com/remote-dev-jobs",
]

sent_jobs = set()

def scrape_indeed():
    url = "https://www.indeed.com/q-IT-jobs.html"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    jobs = []

    for div in soup.find_all(name="div", attrs={"class":"cardOutline"}):
        title = div.find("h2")
        if title:
            link_tag = title.find("a")
            if link_tag and link_tag.has_attr('href'):
                link = "https://indeed.com" + link_tag["href"]
                job_title = title.get_text(strip=True)
                jobs.append((job_title, link))
    return jobs

def scrape_monster():
    url = "https://www.monster.com/jobs/search/?q=IT&where="
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    jobs = []

    for div in soup.find_all('section', attrs={'class': 'card-content'}):
        title = div.find('h2', attrs={'class': 'title'})
        if title and title.a:
            link = title.a['href']
            job_title = title.text.strip()
            jobs.append((job_title, link))
    return jobs

def scrape_remoteok():
    url = "https://remoteok.com/remote-dev-jobs"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    jobs = []

    for tr in soup.find_all('tr', {'class': 'job'}):
        a_tag = tr.find('a', {'itemprop': 'url'})
        if a_tag:
            link = "https://remoteok.com" + a_tag['href']
            title_tag = tr.find('h2', {'itemprop': 'title'})
            if title_tag:
                job_title = title_tag.get_text(strip=True)
                jobs.append((job_title, link))
    return jobs

async def send_new_jobs():
    bot = Bot(BOT_TOKEN)

    all_jobs = scrape_indeed() + scrape_monster() + scrape_remoteok()

    for job_title, link in all_jobs:
        unique_id = f"{job_title}_{link}"
        if unique_id not in sent_jobs:
            sent_jobs.add(unique_id)
            message = f"💼 *{job_title}*\n🔗 [Apply Here]({link})"
            try:
                await bot.send_message(
                    chat_id=CHAT_ID,
                    text=message,
                    parse_mode='Markdown',
                    disable_web_page_preview=False
                )
            except Exception as e:
                print(f"Error sending job: {e}")

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: asyncio.run(send_new_jobs()), 'interval', minutes=2)
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

    start_scheduler()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    print("Bot started and polling...")
    await app.run_polling()

if __name__ == "__main__":
    print("Bot is starting...")
    asyncio.run(main())
