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
import json
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
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")  # Custom Search Engine ID

# File to store user data
USERS_FILE = "users.json"

# Global variables
sent_jobs = set()
scheduler = None
subscribed_users = set()

# Load subscribed users from file
def load_users():
    global subscribed_users
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                users_data = json.load(f)
                subscribed_users = set(users_data.get('users', []))
                logger.info(f"Loaded {len(subscribed_users)} subscribed users")
    except Exception as e:
        logger.error(f"Error loading users: {e}")
        subscribed_users = set()

# Save subscribed users to file
def save_users():
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump({'users': list(subscribed_users)}, f)
        logger.info(f"Saved {len(subscribed_users)} subscribed users")
    except Exception as e:
        logger.error(f"Error saving users: {e}")

# Google Custom Search API for IT jobs
def search_google_jobs():
    try:
        if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
            logger.warning("Google API credentials not set, skipping Google job search")
            return []
            
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
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        jobs = []
        
        # Try multiple possible selectors for Indeed's layout
        job_cards = soup.select("div.job_seen_beacon") or soup.select("div.tapItem")
        
        for card in job_cards:
            title_elem = card.select_one("h2.jobTitle") or card.select_one("h2.title")
            if title_elem:
                title = title_elem.get_text(strip=True)
                link_elem = title_elem.find("a")
                if link_elem and link_elem.has_attr('href'):
                    job_id = link_elem.get('data-jk') or link_elem.get('id', '').replace('job_', '')
                    if job_id:
                        link = f"https://www.indeed.com/viewjob?jk={job_id}"
                        jobs.append((title, link))
        
        logger.info(f"Scraped {len(jobs)} jobs from Indeed")
        return jobs
    except Exception as e:
        logger.error(f"Error scraping Indeed: {e}")
        return []

def scrape_linkedin():
    try:
        url = "https://www.linkedin.com/jobs/search/?keywords=IT"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        jobs = []
        
        job_cards = soup.select("div.base-card") or soup.select("li.job-search-card")
        for card in job_cards:
            title_elem = card.select_one("h3.base-search-card__title") or card.select_one("h3.job-search-card__title")
            link_elem = card.select_one("a.base-card__full-link") or card.select_one("a.job-search-card__link")
            
            if title_elem and link_elem:
                title = title_elem.get_text(strip=True)
                link = link_elem.get('href', '').split('?')[0]  # Remove query params
                if title and link:
                    jobs.append((title, link))
                    
        logger.info(f"Scraped {len(jobs)} jobs from LinkedIn")
        return jobs
    except Exception as e:
        logger.error(f"Error scraping LinkedIn: {e}")
        return []

def scrape_remoteok():
    try:
        url = "https://remoteok.com/remote-dev-jobs"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://remoteok.com/"
        }
        response = requests.get(url, headers=headers, timeout=20)  # Increased timeout
        soup = BeautifulSoup(response.text, "html.parser")
        jobs = []
        
        for tr in soup.find_all('tr', class_='job'):
            try:
                a_tag = tr.find('a', itemprop='url')
                if a_tag:
                    link = "https://remoteok.com" + a_tag['href']
                    title_tag = tr.find('h2', itemprop='title')
                    if title_tag:
                        job_title = title_tag.get_text(strip=True)
                        jobs.append((job_title, link))
            except Exception as job_error:
                logger.error(f"Error parsing RemoteOK job: {job_error}")
                continue
                
        logger.info(f"Scraped {len(jobs)} jobs from RemoteOK")
        return jobs
    except requests.exceptions.Timeout:
        logger.error("RemoteOK request timed out")
        return []
    except Exception as e:
        logger.error(f"Error scraping RemoteOK: {e}")
        return []

def scrape_stackoverflow():
    try:
        url = "https://stackoverflow.com/jobs?q=IT"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        jobs = []
        
        for div in soup.select("div.listResults div.-job"):
            title_elem = div.select_one("h2 a")
            if title_elem:
                title = title_elem.get_text(strip=True)
                link = f"https://stackoverflow.com{title_elem['href']}"
                jobs.append((title, link))
                
        logger.info(f"Scraped {len(jobs)} jobs from StackOverflow")
        return jobs
    except Exception as e:
        logger.error(f"Error scraping StackOverflow: {e}")
        return []

async def send_new_jobs():
    try:
        if not subscribed_users:
            logger.info("No subscribed users to send jobs to")
            return
            
        bot = Bot(BOT_TOKEN)
        
        # Collect jobs from all sources
        all_jobs = []
        all_jobs.extend(scrape_indeed())
        all_jobs.extend(scrape_linkedin())
        all_jobs.extend(scrape_remoteok())
        all_jobs.extend(scrape_stackoverflow())
        
        # Add Google jobs if API credentials are available
        if GOOGLE_API_KEY and GOOGLE_CSE_ID:
            all_jobs.extend(search_google_jobs())
        
        logger.info(f"Total jobs collected: {len(all_jobs)}")
        
        new_jobs = []
        for job_title, link in all_jobs:
            unique_id = f"{job_title}_{link}"
            if unique_id not in sent_jobs:
                sent_jobs.add(unique_id)
                # Clean job title of any special characters that might break Markdown
                job_title = job_title.replace("*", "").replace("_", "").replace("`", "").replace("[", "").replace("]", "")
                new_jobs.append((job_title, link))
        
        if not new_jobs:
            logger.info("No new jobs to send")
            return
            
        logger.info(f"Found {len(new_jobs)} new jobs to send to {len(subscribed_users)} users")
        
        # Send each new job to all subscribed users
        for user_id in list(subscribed_users):  # Create a copy of the list to safely modify during iteration
            try:
                jobs_sent = 0
                for job_title, link in new_jobs:
                    message = f"💼 *{job_title}*\n🔗 [Apply Here]({link})\n⏰ Posted: {datetime.now().strftime('%Y-%m-%d')}"
                    try:
                        await bot.send_message(
                            chat_id=user_id,
                            text=message,
                            parse_mode='Markdown',
                            disable_web_page_preview=False
                        )
                        jobs_sent += 1
                        # Small delay to avoid flooding
                        await asyncio.sleep(0.3)
                    except Exception as e:
                        if "blocked" in str(e).lower() or "not found" in str(e).lower() or "chat not found" in str(e).lower():
                            logger.warning(f"User {user_id} has blocked the bot or deleted their account, removing from subscribers")
                            subscribed_users.discard(user_id)
                            save_users()
                        else:
                            logger.error(f"Error sending job to user {user_id}: {e}")
                
                if jobs_sent > 0:
                    logger.info(f"Sent {jobs_sent} new jobs to user {user_id}")
            except Exception as user_error:
                logger.error(f"Error processing user {user_id}: {user_error}")
                
    except Exception as e:
        logger.error(f"Error in send_new_jobs: {e}")

def start_scheduler(app):
    global scheduler
    
    if scheduler:
        scheduler.shutdown(wait=False)
    
    scheduler = BackgroundScheduler()

    def sync_send_jobs():
        asyncio.create_task(send_new_jobs())

    scheduler.add_job(sync_send_jobs, 'interval', minutes=1)  # Check every 30 minutes
    scheduler.start()
    logger.info("Scheduler started...")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Subscribe a user when they use the /start command."""
    user_id = update.effective_chat.id
    
    if user_id not in subscribed_users:
        subscribed_users.add(user_id)
        save_users()
        await update.message.reply_text(
            'Welcome to the IT Job Alert Bot! 🚀\n\n'
            'You will now receive IT job updates every 30 minutes.\n\n'
            'Type /help to see all available commands.'
        )
    else:
        await update.message.reply_text(
            'You are already subscribed to job alerts! 📝\n'
            'You will continue to receive job updates every 30 minutes.'
        )

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unsubscribe a user when they use the /stop command."""
    user_id = update.effective_chat.id
    
    if user_id in subscribed_users:
        subscribed_users.discard(user_id)
        save_users()
        await update.message.reply_text('You have been unsubscribed from job alerts. Goodbye! 👋')
    else:
        await update.message.reply_text('You are not currently subscribed to job alerts.')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send help information when /help command is issued."""
    help_text = """
*IT Job Alert Bot - Commands*

/start - Subscribe to job alerts
/stop - Unsubscribe from job alerts
/help - Show this help message
/jobs - Check for new jobs now
/status - Check bot status and subscription info

The bot automatically checks for new IT jobs every 30 minutes and sends them directly to you.

Job sources include: Indeed, LinkedIn, RemoteOK, StackOverflow, and Google Jobs.
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check the status of the bot and user subscription."""
    user_id = update.effective_chat.id
    
    subscription_status = "🟢 Subscribed" if user_id in subscribed_users else "🔴 Not subscribed"
    
    if scheduler and scheduler.running:
        bot_status = "🟢 Bot is running"
    else:
        bot_status = "🔴 Bot is not running"
        
    total_subscribers = len(subscribed_users)
    
    stats = f"""
*Bot Status:*
{bot_status}
{subscription_status} to job alerts
Total subscribers: {total_subscribers}
Jobs in memory: {len(sent_jobs)}
Update frequency: Every 30 minutes
    """
    await update.message.reply_text(stats, parse_mode='Markdown')

async def force_job_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Force a job check when /jobs command is issued."""
    user_id = update.effective_chat.id
    
    if user_id not in subscribed_users:
        await update.message.reply_text('You need to subscribe first. Use /start to subscribe to job alerts.')
        return
        
    await update.message.reply_text('Checking for new jobs...')
    
    # Perform a special check for just this user
    try:
        bot = Bot(BOT_TOKEN)
        
        # Collect jobs from all sources
        all_jobs = []
        all_jobs.extend(scrape_indeed())
        all_jobs.extend(scrape_linkedin())
        all_jobs.extend(scrape_remoteok())
        all_jobs.extend(scrape_stackoverflow())
        
        # Add Google jobs if API credentials are available
        if GOOGLE_API_KEY and GOOGLE_CSE_ID:
            all_jobs.extend(search_google_jobs())
        
        # Send the 10 most recent jobs to just this user
        jobs_sent = 0
        sample_jobs = all_jobs[:10]  # Get the 10 most recent jobs
        
        for job_title, link in sample_jobs:
            # Add to global sent jobs to avoid duplicates later
            unique_id = f"{job_title}_{link}"
            sent_jobs.add(unique_id)
            
            # Clean job title of any special characters that might break Markdown
            job_title = job_title.replace("*", "").replace("_", "").replace("`", "").replace("[", "").replace("]", "")
            message = f"💼 *{job_title}*\n🔗 [Apply Here]({link})\n⏰ Posted: {datetime.now().strftime('%Y-%m-%d')}"
            
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode='Markdown',
                    disable_web_page_preview=False
                )
                jobs_sent += 1
                # Small delay to avoid flooding
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.error(f"Error sending job to user {user_id}: {e}")
        
        if jobs_sent > 0:
            await update.message.reply_text(f'Sent you {jobs_sent} recent job listings!')
        else:
            await update.message.reply_text('No new jobs found at the moment. Check back later!')
            
    except Exception as e:
        logger.error(f"Error in force job check: {e}")
        await update.message.reply_text(f'Error checking for jobs: {str(e)}')

async def main():
    # Load subscribed users from file
    load_users()
    
    # Set up the application with command handlers
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("jobs", force_job_check))
    app.add_handler(CommandHandler("status", status_command))
    
    # Start the scheduler
    start_scheduler(app)
    
    # Run initial job check if there are subscribed users
    if subscribed_users:
        asyncio.create_task(send_new_jobs())
    
    # Run the bot
    logger.info(f"Bot started and polling with {len(subscribed_users)} subscribed users")
    await app.run_polling()

if __name__ == "__main__":
    logger.info("Bot is starting...")
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot is shutting down...")
        # Save users before shutting down
        save_users()
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        # Save users even on crash
        save_users()