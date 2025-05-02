import os
import requests
from bs4 import BeautifulSoup
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
import asyncio
import nest_asyncio
import logging
from datetime import datetime, timedelta
import json
from googleapiclient.discovery import build
import re
import time

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Apply Railway event loop fix
nest_asyncio.apply()

# Environment variables
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")
LINKEDIN_USERNAME = os.getenv("LINKEDIN_USERNAME")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")

# File to store user data
USERS_FILE = "users.json"

# Global variables
sent_jobs = set()
scheduler = None
subscribed_users = set()

# Target job roles for freshers/entry-level
TARGET_ROLES = [
    "developer", "software developer", "web developer", "frontend developer", "backend developer", 
    "data analyst", "business analyst", "data scientist", "junior data analyst",
    "tester", "qa tester", "software tester", "test engineer", "qa engineer",
    "cybersecurity", "security analyst", "information security", "cyber security",
    "ui designer", "ux designer", "ui/ux designer", "ui ux", "product designer",
    "junior developer", "graduate developer", "entry level developer",
    "fresher", "entry level", "junior", "graduate", "trainee", "hiring", "openings",
    "recruitment", "we are hiring", "job opening", "opportunity"
]

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

# Check if a job matches target roles
def is_target_job(job_title):
    job_title_lower = job_title.lower()
    return any(role in job_title_lower for role in TARGET_ROLES)

# Check if a job posting is recent (within the last 7 days)
def is_recent_job(date_str=None):
    if not date_str:
        return True  # If no date, assume it's recent
        
    try:
        # Try to parse common date formats
        date_formats = [
            "%Y-%m-%d", "%d-%m-%Y", "%m-%d-%Y", "%d/%m/%Y", "%m/%d/%Y",
            "%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y"
        ]
        
        for fmt in date_formats:
            try:
                job_date = datetime.strptime(date_str, fmt)
                break
            except ValueError:
                continue
        else:
            # Check for relative dates like "2 days ago", "yesterday", etc.
            if "today" in date_str.lower() or "just now" in date_str.lower():
                return True
            elif "yesterday" in date_str.lower():
                return True
            elif "ago" in date_str.lower():
                # Extract the number and unit from string like "3 days ago"
                match = re.search(r'(\d+)\s+(day|hour|minute|second|week)s?\s+ago', date_str.lower())
                if match:
                    num, unit = int(match.group(1)), match.group(2)
                    if unit == "week" and num <= 1:
                        return True
                    elif unit in ["day", "hour", "minute", "second"]:
                        return True
                return False
            else:
                return True  # If we can't parse the date, assume it's recent
                
        # Check if date is within the last 7 days
        return (datetime.now() - job_date).days <= 7
    except Exception:
        return True  # If any error, assume job is recent

# Google Custom Search API for recent entry-level jobs
def search_google_jobs():
    try:
        if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
            return []
            
        service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
        jobs = []
        
        # Focus on very recent jobs
        search_queries = [
            "entry level developer jobs", 
            "junior data analyst jobs", 
            "junior software tester jobs",
            "entry level cybersecurity jobs", 
            "junior ui ux designer jobs"
        ]
        
        for query in search_queries[:2]:  # Limit to 2 queries
            try:
                result = service.cse().list(
                    q=f"{query} posted today this week",
                    cx=GOOGLE_CSE_ID,
                    num=5,
                    dateRestrict="d7"  # Last 7 days
                ).execute()
                
                if "items" in result:
                    for item in result["items"]:
                        title = item["title"]
                        link = item["link"]
                        if is_target_job(title):
                            jobs.append((title, link, "Recent"))
            except Exception as e:
                logger.error(f"Error in Google search: {e}")
                continue
                
        return jobs
    except Exception as e:
        logger.error(f"Error searching Google jobs: {e}")
        return []

async def scrape_indeed():
    try:
        jobs = []
        search_terms = [
            "entry+level+developer", "junior+developer", 
            "entry+level+data+analyst", "entry+level+tester"
        ]
        
        for term in search_terms[:2]:  # Limit to avoid too many requests
            try:
                # Add date filter to URL
                url = f"https://www.indeed.com/jobs?q={term}&sort=date&fromage=7"  # Jobs from last 7 days
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                response = requests.get(url, headers=headers, timeout=15)
                soup = BeautifulSoup(response.text, "html.parser")
                
                job_cards = soup.select("div.job_seen_beacon") or soup.select("div.tapItem")
                
                for card in job_cards:
                    title_elem = card.select_one("h2.jobTitle") or card.select_one("h2.title")
                    date_elem = card.select_one("span.date") or card.select_one(".date")
                    
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        
                        # Extract date if available
                        post_date = date_elem.get_text(strip=True) if date_elem else "Recent"
                        
                        link_elem = title_elem.find("a")
                        if link_elem and link_elem.has_attr('href'):
                            job_id = link_elem.get('data-jk') or link_elem.get('id', '').replace('job_', '')
                            if job_id:
                                link = f"https://www.indeed.com/viewjob?jk={job_id}"
                                if is_target_job(title) and is_recent_job(post_date):
                                    jobs.append((title, link, post_date))
                
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error scraping Indeed: {e}")
                continue
        
        return jobs
    except Exception as e:
        logger.error(f"Error in Indeed scraper: {e}")
        return []

async def scrape_linkedin():
    try:
        jobs = []
        search_terms = [
            "entry-level-developer", "junior-data-analyst", 
            "entry-level-tester", "junior-ui-ux-designer"
        ]
        
        for term in search_terms[:2]:
            try:
                # Use LinkedIn's date filter parameter
                url = f"https://www.linkedin.com/jobs/search/?keywords={term}&f_E=2&f_TPR=r604800&sortBy=DD"  # f_E=2 is entry level, f_TPR=r604800 is past week
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                response = requests.get(url, headers=headers, timeout=15)
                soup = BeautifulSoup(response.text, "html.parser")
                
                job_cards = soup.select("div.base-card") or soup.select("li.job-search-card")
                for card in job_cards:
                    title_elem = card.select_one("h3.base-search-card__title") or card.select_one("h3.job-search-card__title")
                    date_elem = card.select_one("time") or card.select_one(".job-search-card__listdate")
                    link_elem = card.select_one("a.base-card__full-link") or card.select_one("a.job-search-card__link")
                    
                    if title_elem and link_elem:
                        title = title_elem.get_text(strip=True)
                        post_date = date_elem.get_text(strip=True) if date_elem else "Recent"
                        link = link_elem.get('href', '').split('?')[0]
                        
                        if title and link and is_target_job(title) and is_recent_job(post_date):
                            jobs.append((title, link, post_date))
                
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error scraping LinkedIn: {e}")
                continue
                    
        return jobs
    except Exception as e:
        logger.error(f"Error in LinkedIn scraper: {e}")
        return []

async def scrape_linkedin_posts():
    """Scrape LinkedIn company posts for job announcements"""
    try:
        jobs = []
        search_terms = [
            "hiring freshers", "hiring graduates", "job openings", 
            "career opportunity", "we are hiring"
        ]
        
        for term in search_terms[:2]:  # Limit to avoid rate limiting
            try:
                # Search for company posts mentioning hiring
                url = f"https://www.linkedin.com/search/results/content/?keywords={term}&origin=GLOBAL_SEARCH_HEADER&sortBy=date_posted"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://www.linkedin.com/"
                }
                
                response = requests.get(url, headers=headers, timeout=20)
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Look for feed posts
                post_cards = soup.select("div.feed-shared-update-v2") or soup.select("li.reusable-search__result-container")
                
                for card in post_cards:
                    try:
                        # Extract post content
                        content_elem = card.select_one("div.feed-shared-text") or card.select_one("div.feed-shared-update-v2__description")
                        title_elem = card.select_one("span.feed-shared-actor__title") or card.select_one("span.update-components-actor__title")
                        
                        if not content_elem:
                            continue
                            
                        content = content_elem.get_text(strip=True)
                        company = title_elem.get_text(strip=True) if title_elem else "Company"
                        
                        # Check if content mentions job opportunities
                        if any(keyword.lower() in content.lower() for keyword in TARGET_ROLES):
                            # Find post link
                            link_elem = card.select_one("a.app-aware-link") or card.select_one("a.feed-shared-actor__container-link")
                            if link_elem and link_elem.has_attr('href'):
                                post_link = link_elem.get('href', '').split('?')[0]
                                
                                # Clean and truncate content for title
                                job_title = f"{company}: {content[:50]}..." if len(content) > 50 else f"{company}: {content}"
                                
                                # Get date if available
                                date_elem = card.select_one("span.feed-shared-actor__sub-description") or card.select_one("time")
                                post_date = date_elem.get_text(strip=True) if date_elem else "Recent"
                                
                                if post_link and is_recent_job(post_date):
                                    jobs.append((job_title, post_link, post_date))
                    except Exception as e:
                        logger.error(f"Error processing LinkedIn post: {e}")
                        continue
                
                await asyncio.sleep(2)  # Be nice to LinkedIn
            except Exception as e:
                logger.error(f"Error scraping LinkedIn posts: {e}")
                continue
                
        return jobs
    except Exception as e:
        logger.error(f"Error in LinkedIn posts scraper: {e}")
        return []

async def scrape_remoteok():
    try:
        jobs = []
        search_terms = ["junior-dev", "entry-dev", "junior-data", "junior-security", "ui-ux"]
        
        for term in search_terms[:2]:
            try:
                url = f"https://remoteok.com/remote-{term}-jobs"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                response = requests.get(url, headers=headers, timeout=20)
                soup = BeautifulSoup(response.text, "html.parser")
                
                for tr in soup.find_all('tr', class_='job'):
                    try:
                        a_tag = tr.find('a', itemprop='url')
                        if a_tag:
                            link = "https://remoteok.com" + a_tag['href']
                            title_tag = tr.find('h2', itemprop='title')
                            date_tag = tr.find('td', class_='time')
                            
                            if title_tag:
                                job_title = title_tag.get_text(strip=True)
                                post_date = date_tag.get_text(strip=True) if date_tag else "Recent"
                                
                                if is_target_job(job_title) and is_recent_job(post_date):
                                    jobs.append((job_title, link, post_date))
                    except Exception:
                        continue
                
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error scraping RemoteOK: {e}")
                continue
                
        return jobs
    except Exception as e:
        logger.error(f"Error in RemoteOK scraper: {e}")
        return []

# Function to update job sources every minute (rotating through sources)
async def check_job_source(source_name):
    logger.info(f"Checking job source: {source_name}")
    jobs = []
    
    if source_name == "indeed":
        jobs = await scrape_indeed()
    elif source_name == "linkedin_jobs":
        jobs = await scrape_linkedin()
    elif source_name == "linkedin_posts":
        jobs = await scrape_linkedin_posts()
    elif source_name == "remoteok":
        jobs = await scrape_remoteok()
    elif source_name == "google":
        if GOOGLE_API_KEY and GOOGLE_CSE_ID:
            jobs = search_google_jobs()
            
    if jobs:
        await send_jobs_to_users(jobs)

# Create a rotation of job sources to check
def rotate_job_sources():
    sources = ["indeed", "linkedin_jobs", "linkedin_posts", "remoteok", "google"]
    current_index = 0
    
    def get_next_source():
        nonlocal current_index
        source = sources[current_index]
        current_index = (current_index + 1) % len(sources)
        return source
    
    return get_next_source

async def send_jobs_to_users(jobs):
    try:
        if not subscribed_users or not jobs:
            return
            
        bot = Bot(BOT_TOKEN)
        
        # Filter for recent, relevant and new jobs
        new_jobs = []
        for job_data in jobs:
            job_title, link = job_data[0], job_data[1]
            post_date = job_data[2] if len(job_data) > 2 else "Recent"
            
            # Check if we've seen this job before
            unique_id = f"{job_title}_{link}"
            if unique_id not in sent_jobs:
                sent_jobs.add(unique_id)
                # Clean job title of any special characters for Markdown
                job_title = job_title.replace("*", "").replace("_", "").replace("`", "").replace("[", "").replace("]", "")
                new_jobs.append((job_title, link, post_date))
        
        if not new_jobs:
            return
            
        logger.info(f"Found {len(new_jobs)} new recent jobs to send to {len(subscribed_users)} users")
        
        # Send each new job to all subscribed users
        for user_id in list(subscribed_users):
            try:
                jobs_sent = 0
                for job_title, link, post_date in new_jobs:
                    message = f"💼 *{job_title}*\n🔗 [Apply Here]({link})\n⏰ Posted: {post_date}"
                    try:
                        await bot.send_message(
                            chat_id=user_id,
                            text=message,
                            parse_mode='Markdown',
                            disable_web_page_preview=False
                        )
                        jobs_sent += 1
                        await asyncio.sleep(0.3)
                    except Exception as e:
                        if "blocked" in str(e).lower() or "not found" in str(e).lower():
                            logger.warning(f"User {user_id} has blocked the bot or deleted account, removing")
                            subscribed_users.discard(user_id)
                            save_users()
                        else:
                            logger.error(f"Error sending job to user {user_id}: {e}")
                
                if jobs_sent > 0:
                    logger.info(f"Sent {jobs_sent} new jobs to user {user_id}")
            except Exception as e:
                logger.error(f"Error processing user {user_id}: {e}")
                
    except Exception as e:
        logger.error(f"Error in send_jobs_to_users: {e}")

def start_scheduler():
    global scheduler
    
    if scheduler:
        scheduler.shutdown(wait=False)
    
    scheduler = BackgroundScheduler()
    get_next_source = rotate_job_sources()

    # Function that runs every minute to check one job source
    def check_next_source():
        source = get_next_source()
        asyncio.create_task(check_job_source(source))

    # Run every minute
    scheduler.add_job(check_next_source, 'interval', minutes=1)
    
    # Limit the number of jobs we keep in memory (to prevent memory leaks)
    def cleanup_job_cache():
        global sent_jobs
        if len(sent_jobs) > 1000:
            # Keep only the most recent 500 jobs
            sent_jobs = set(list(sent_jobs)[-500:])
    
    scheduler.add_job(cleanup_job_cache, 'interval', hours=12)
    
    scheduler.start()
    logger.info("Scheduler started - checking one job source every minute...")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    
    if user_id not in subscribed_users:
        subscribed_users.add(user_id)
        save_users()
        await update.message.reply_text(
            'Welcome to the Entry-Level IT Job Alert Bot! 🚀\n\n'
            'You will now receive recent entry-level IT job updates every minute.\n\n'
            'Type /help to see all available commands.'
        )
    else:
        await update.message.reply_text('You are already subscribed to job alerts! 📝')

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    
    if user_id in subscribed_users:
        subscribed_users.discard(user_id)
        save_users()
        await update.message.reply_text('Varta mame durrrrr👋')
    else:
        await update.message.reply_text('You are not currently subscribed to job alerts.')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
*Entry-Level IT Job Alert Bot - Commands*

/start - Subscribe to job alerts
/stop - Unsubscribe from job alerts
/help - Show this help message
/jobs - Check for new jobs now
/status - Check bot status

The bot automatically checks for recent entry-level IT jobs every minute from global sources. We focus on the past week's job postings for freshers and entry-level roles.
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    
    subscription_status = "🟢 Subscribed" if user_id in subscribed_users else "🔴 Not subscribed"
    bot_status = "🟢 Bot is running" if scheduler and scheduler.running else "🔴 Bot is not running"
    total_subscribers = len(subscribed_users)
    
    stats = f"""
*Bot Status:*
{bot_status}
{subscription_status} to job alerts
Total subscribers: {total_subscribers}
Jobs in memory: {len(sent_jobs)}
Update frequency: Every minute
Focus: Recent entry-level IT jobs (past week)
    """
    await update.message.reply_text(stats, parse_mode='Markdown')

async def force_job_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    
    if user_id not in subscribed_users:
        await update.message.reply_text('You need to subscribe first. Use /start to subscribe to job alerts.')
        return
        
    await update.message.reply_text('Wait panu mame search panran🕵️')
    
    try:
        bot = Bot(BOT_TOKEN)
        
        # Collect recent jobs from all sources
        all_jobs = []
        all_jobs.extend(await scrape_indeed())
        all_jobs.extend(await scrape_linkedin())
        all_jobs.extend(await scrape_linkedin_posts())  # Include LinkedIn posts!
        all_jobs.extend(await scrape_remoteok())
        
        # Add Google jobs if API credentials are available
        if GOOGLE_API_KEY and GOOGLE_CSE_ID:
            all_jobs.extend(search_google_jobs())
        
        # Filter for relevant jobs
        filtered_jobs = []
        for job_data in all_jobs:
            title, link = job_data[0], job_data[1]
            post_date = job_data[2] if len(job_data) > 2 else "Recent"
            
            # Add to global sent jobs to avoid duplicates
            unique_id = f"{title}_{link}"
            sent_jobs.add(unique_id)
            
            # Clean job title for Markdown
            title = title.replace("*", "").replace("_", "").replace("`", "").replace("[", "").replace("]", "")
            filtered_jobs.append((title, link, post_date))
        
        # Send jobs to this specific user
        jobs_sent = 0
        for job_title, link, post_date in filtered_jobs:
            message = f"💼 *{job_title}*\n🔗 [Apply Here]({link})\n⏰ Posted: {post_date}"
            
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode='Markdown',
                    disable_web_page_preview=False
                )
                jobs_sent += 1
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.error(f"Error sending job to user {user_id}: {e}")
        
        if jobs_sent > 0:
            await update.message.reply_text(f'Search pana matum podhadhu, Apply pananum😁')
        else:
            await update.message.reply_text('No new entry-level IT jobs found at the moment. Check back later!')
            
    except Exception as e:
        logger.error(f"Error in force job check: {e}")
        await update.message.reply_text('Error checking for jobs. Please try again later.')

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
    start_scheduler()
    
    # Run the bot
    logger.info(f"Bot started and polling with {len(subscribed_users)} subscribed users")
    await app.run_polling()

if __name__ == "__main__":
    logger.info("Recent Entry-Level IT Jobs Bot is starting...")
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot is shutting down...")
        save_users()
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        save_users()