import os
import requests
from bs4 import BeautifulSoup
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
import asyncio
import nest_asyncio
import logging
from datetime import datetime
from googleapiclient.discovery import build

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Apply Railway event loop fix
nest_asyncio.apply()

# Environment variables
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")  # Custom Search Engine ID

# Global variables
sent_jobs = set()
scheduler = None

# Google Custom Search API for IT jobs
def search_google_jobs():
    try:
        service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        # Search for recent IT job postings
        result = service.cse().list(
            q=f"IT jobs {date_str}",
            cx=GOOGLE_CSE_ID,
            num=10,
            dateRestrict="d1"  # Last 24 hours
        ).execute()
        
        jobs = []
        if "items" in result:
            for item in result["items"]:
                title = item["title"]
                link = item["link"]
                jobs.append((title, link))
        return jobs
    except Exception as e:
        logger.error(f"Error searching Google jobs: {e}")
        return []

def scrape_indeed():
    try:
        url = "https://www.indeed.com/q-IT-jobs.html"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        jobs = []
        
        # Updated selectors for Indeed's current layout
        job_cards = soup.select("div.job_seen_beacon")
        for card in job_cards:
            title_elem = card.select_one("h2.jobTitle")
            if title_elem:
                title = title_elem.get_text(strip=True)
                link_elem = title_elem.find("a")
                if link_elem and link_elem.has_attr('href'):
                    job_id = link_elem.get('data-jk') or link_elem.get('id', '').replace('job_', '')
                    if job_id:
                        link = f"https://www.indeed.com/viewjob?jk={job_id}"
                        jobs.append((title, link))
        return jobs
    except Exception as e:
        logger.error(f"Error scraping Indeed: {e}")
        return []

def scrape_linkedin():
    try:
        url = "https://www.linkedin.com/jobs/search/?keywords=IT"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        jobs = []
        
        job_cards = soup.select("div.base-card")
        for card in job_cards:
            title_elem = card.select_one("h3.base-search-card__title")
            link_elem = card.select_one("a.base-card__full-link")
            
            if title_elem and link_elem:
                title = title_elem.get_text(strip=True)
                link = link_elem.get('href', '').split('?')[0]  # Remove query params
                if title and link:
                    jobs.append((title, link))
        return jobs
    except Exception as e:
        logger.error(f"Error scraping LinkedIn: {e}")
        return []

def scrape_remoteok():
    try:
        url = "https://remoteok.com/remote-dev-jobs"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        response = requests.get(url, headers=headers, timeout=10)
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
    except Exception as e:
        logger.error(f"Error scraping RemoteOK: {e}")
        return []

async def send_new_jobs():
    bot = Bot(BOT_TOKEN)
    
    # Collect jobs from all sources
    all_jobs = []
    all_jobs.extend(scrape_indeed())
    all_jobs.extend(scrape_linkedin())
    all_jobs.extend(scrape_remoteok())
    
    # Add Google jobs if API credentials are available
    if GOOGLE_API_KEY and GOOGLE_CSE_ID:
        all_jobs.extend(search_google_jobs())
    
    jobs_sent = 0
    for job_title, link in all_jobs:
        unique_id = f"{job_title}_{link}"
        if unique_id not in sent_jobs:
            sent_jobs.add(unique_id)
            message = f"💼 *{job_title}*\n🔗 [Apply Here]({link})\n⏰ Posted: {datetime.now().strftime('%Y-%m-%d')}"
            try:
                await bot.send_message(
                    chat_id=CHAT_ID,
                    text=message,
                    parse_mode='Markdown',
                    disable_web_page_preview=False
                )
                jobs_sent += 1
                # Small delay to avoid flooding
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Error sending job: {e}")
    
    logger.info(f"Sent {jobs_sent} new job listings")

def start_scheduler(app):
    global scheduler
    scheduler = BackgroundScheduler()

    def sync_send_jobs():
        asyncio.create_task(send_new_jobs())

    scheduler.add_job(sync_send_jobs, 'interval', minutes=30)  # Changed to 30 minutes to avoid rate limits
    scheduler.start()
    logger.info("Scheduler started...")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    await update.message.reply_text('Job search bot started! You will receive IT job updates every 30 minutes.')

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop the bot when /stop command is issued."""
    global scheduler
    if scheduler:
        scheduler.shutdown()
        scheduler = None
        await update.message.reply_text('Job search bot stopped!')
    else:
        await update.message.reply_text('Bot is not currently running.')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send help information when /help command is issued."""
    help_text = """
*Available commands:*
/start - Start receiving job updates
/stop - Stop receiving job updates
/help - Show this help message
/jobs - Force check for new jobs now
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def force_job_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Force a job check when /jobs command is issued."""
    await update.message.reply_text('Checking for new jobs...')
    await send_new_jobs()
    await update.message.reply_text('Job check completed!')

async def main():
    global CHAT_ID
    
    # Set up the application with command handlers
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("jobs", force_job_check))
    
    # Start the scheduler
    start_scheduler(app)
    
    # Detect chat_id if not set
    if not CHAT_ID:
        bot = Bot(BOT_TOKEN)
        updates = await bot.get_updates()
        if updates:
            CHAT_ID = updates[-1].message.chat_id
            logger.info(f"Detected CHAT_ID automatically: {CHAT_ID}")
    
    # Run initial job check
    await send_new_jobs()
    
    # Run the bot
    logger.info("Bot started and polling...")
    await app.run_polling()

if __name__ == "__main__":
    logger.info("Bot is starting...")
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot is shutting down...")