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

# Target job roles for freshers/entry-level
TARGET_ROLES = [
    "developer", "software developer", "web developer", "frontend developer", "backend developer", 
    "data analyst", "business analyst", "data scientist", "junior data analyst",
    "tester", "qa tester", "software tester", "test engineer", "qa engineer",
    "cybersecurity", "security analyst", "information security", "cyber security",
    "ui designer", "ux designer", "ui/ux designer", "ui ux", "product designer",
    "junior developer", "graduate developer", "entry level developer",
    "fresher", "entry level", "junior", "graduate", "trainee"
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
    # Check if any target role is in the job title
    return any(role in job_title_lower for role in TARGET_ROLES)

# Google Custom Search API for targeted entry-level jobs
def search_google_jobs():
    try:
        if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
            logger.warning("Google API credentials not set, skipping Google job search")
            return []
            
        service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
        date_str = datetime.now().strftime("%Y-%m-%d")
        jobs = []
        
        # Search for each target role separately to get more specific results
        for role in ["developer fresher", "data analyst entry level", "software tester junior", 
                    "cybersecurity entry level", "ui ux designer junior"]:
            try:
                result = service.cse().list(
                    q=f"{role} jobs {date_str}",
                    cx=GOOGLE_CSE_ID,
                    num=5,  # Get fewer results per role but more variety
                    dateRestrict="d3"  # Last 3 days for fresher roles which may not update as frequently
                ).execute()
                
                if "items" in result:
                    for item in result["items"]:
                        title = item["title"]
                        link = item["link"]
                        # Only add jobs that match our target criteria
                        if is_target_job(title):
                            jobs.append((title, link))
                # Add a small delay between API calls - remove await here since this isn't an async function
                asyncio.sleep(0.5)
            except Exception as role_error:
                logger.error(f"Error searching Google jobs for role {role}: {role_error}")
                continue
                
        return jobs
    except Exception as e:
        logger.error(f"Error searching Google jobs: {e}")
        return []

async def scrape_indeed():
    try:
        jobs = []
        
        # Search for multiple job types with fresher/entry-level focus
        search_terms = [
            "entry+level+developer", "junior+developer", "fresher+developer",
            "entry+level+data+analyst", "junior+data+analyst",
            "entry+level+tester", "junior+qa",
            "entry+level+cybersecurity", "junior+security+analyst",
            "junior+ui+ux+designer", "entry+level+ui+designer"
        ]
        
        for term in search_terms[:3]:  # Limit to avoid too many requests
            try:
                url = f"https://www.indeed.com/jobs?q={term}&sort=date"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9"
                }
                response = requests.get(url, headers=headers, timeout=15)
                soup = BeautifulSoup(response.text, "html.parser")
                
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
                                # Only add if it matches our target criteria
                                if is_target_job(title):
                                    jobs.append((title, link))
                
                # Add a delay between requests to avoid rate limiting
                await asyncio.sleep(1)
            except Exception as term_error:
                logger.error(f"Error scraping Indeed for term {term}: {term_error}")
                continue
        
        logger.info(f"Scraped {len(jobs)} fresher jobs from Indeed")
        return jobs
    except Exception as e:
        logger.error(f"Error scraping Indeed: {e}")
        return []

async def scrape_linkedin():
    try:
        jobs = []
        
        # Search for multiple job types with entry-level focus
        search_terms = [
            "entry-level-developer", "junior-data-analyst", 
            "entry-level-tester", "entry-level-cybersecurity", 
            "junior-ui-ux-designer"
        ]
        
        for term in search_terms[:3]:  # Limit to avoid too many requests
            try:
                url = f"https://www.linkedin.com/jobs/search/?keywords={term}&f_E=2&sortBy=DD"  # f_E=2 is for entry level
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9"
                }
                response = requests.get(url, headers=headers, timeout=15)
                soup = BeautifulSoup(response.text, "html.parser")
                
                job_cards = soup.select("div.base-card") or soup.select("li.job-search-card")
                for card in job_cards:
                    title_elem = card.select_one("h3.base-search-card__title") or card.select_one("h3.job-search-card__title")
                    link_elem = card.select_one("a.base-card__full-link") or card.select_one("a.job-search-card__link")
                    
                    if title_elem and link_elem:
                        title = title_elem.get_text(strip=True)
                        link = link_elem.get('href', '').split('?')[0]  # Remove query params
                        if title and link and is_target_job(title):
                            jobs.append((title, link))
                
                # Add a delay between requests
                await asyncio.sleep(1)
            except Exception as term_error:
                logger.error(f"Error scraping LinkedIn for term {term}: {term_error}")
                continue
                    
        logger.info(f"Scraped {len(jobs)} entry-level jobs from LinkedIn")
        return jobs
    except Exception as e:
        logger.error(f"Error scraping LinkedIn: {e}")
        return []

async def scrape_remoteok():
    try:
        jobs = []
        
        # Search for each target role
        search_terms = ["junior-dev", "entry-dev", "junior-data", "tester", "junior-security", "ui-ux"]
        
        for term in search_terms[:3]:  # Limit to avoid too many requests
            try:
                url = f"https://remoteok.com/remote-{term}-jobs"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://remoteok.com/"
                }
                response = requests.get(url, headers=headers, timeout=20)
                soup = BeautifulSoup(response.text, "html.parser")
                
                for tr in soup.find_all('tr', class_='job'):
                    try:
                        a_tag = tr.find('a', itemprop='url')
                        if a_tag:
                            link = "https://remoteok.com" + a_tag['href']
                            title_tag = tr.find('h2', itemprop='title')
                            if title_tag:
                                job_title = title_tag.get_text(strip=True)
                                # Only add if relevant to our target roles
                                if is_target_job(job_title):
                                    jobs.append((job_title, link))
                    except Exception as job_error:
                        continue
                
                # Add a delay between requests
                await asyncio.sleep(1)
            except Exception as term_error:
                logger.error(f"Error scraping RemoteOK for term {term}: {term_error}")
                continue
                
        logger.info(f"Scraped {len(jobs)} entry-level jobs from RemoteOK")
        return jobs
    except requests.exceptions.Timeout:
        logger.error("RemoteOK request timed out")
        return []
    except Exception as e:
        logger.error(f"Error scraping RemoteOK: {e}")
        return []

async def scrape_stackoverflow():
    try:
        jobs = []
        
        # Search for specific fresher/entry-level job categories
        search_terms = ["junior developer", "entry level data", "junior tester", 
                        "entry level security", "junior ui ux"]
        
        for term in search_terms[:2]:  # Limit to avoid too many requests
            try:
                url = f"https://stackoverflow.com/jobs?q={term.replace(' ', '+')}"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                response = requests.get(url, headers=headers, timeout=15)
                soup = BeautifulSoup(response.text, "html.parser")
                
                for div in soup.select("div.listResults div.-job"):
                    title_elem = div.select_one("h2 a")
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        link = f"https://stackoverflow.com{title_elem['href']}"
                        # Only add if it's a target job
                        if is_target_job(title):
                            jobs.append((title, link))
                
                # Add delay between requests
                await asyncio.sleep(1)
            except Exception as term_error:
                logger.error(f"Error scraping StackOverflow for term {term}: {term_error}")
                continue
                
        logger.info(f"Scraped {len(jobs)} fresher jobs from StackOverflow")
        return jobs
    except Exception as e:
        logger.error(f"Error scraping StackOverflow: {e}")
        return []

# New function to scrape fresher-specific job sites
async def scrape_fresher_job_sites():
    try:
        jobs = []
        
        # Internshala (popular for freshers in some regions)
        try:
            internshala_roles = ["web-development", "data-science", "ui-ux-design", "cyber-security"]
            for role in internshala_roles[:2]:  # Limit to 2 roles to avoid too many requests
                url = f"https://internshala.com/internships/{role}/"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                response = requests.get(url, headers=headers, timeout=15)
                soup = BeautifulSoup(response.text, "html.parser")
                
                containers = soup.select(".internship_meta")
                for container in containers:
                    title_elem = container.select_one("a.view_detail_button")
                    if title_elem:
                        company_elem = container.select_one(".company_name")
                        company = company_elem.get_text(strip=True) if company_elem else "Company"
                        title = f"{title_elem.get_text(strip=True)} at {company}"
                        link = "https://internshala.com" + title_elem.get('href', '')
                        jobs.append((title, link))
                
                await asyncio.sleep(1)  # Delay between requests
        except Exception as e:
            logger.error(f"Error scraping Internshala: {e}")
            
        # Freshersworld (specialized in fresher jobs)
        try:
            fresher_roles = ["software-developer", "data-analyst", "software-tester", 
                             "cyber-security", "ui-designer"]
            for role in fresher_roles[:2]:  # Limit to 2 roles
                url = f"https://www.freshersworld.com/jobs/search?job={role}"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                response = requests.get(url, headers=headers, timeout=15)
                soup = BeautifulSoup(response.text, "html.parser")
                
                job_listings = soup.select(".job-container")
                for job in job_listings:
                    title_elem = job.select_one(".job-title")
                    company_elem = job.select_one(".job-company")
                    link_elem = job.select_one("a")
                    
                    if title_elem and link_elem:
                        company = company_elem.get_text(strip=True) if company_elem else "Company"
                        title = f"{title_elem.get_text(strip=True)} - {company}"
                        link = link_elem.get('href', '')
                        if not link.startswith('http'):
                            link = "https://www.freshersworld.com" + link
                        jobs.append((title, link))
                
                await asyncio.sleep(1)  # Delay between requests
        except Exception as e:
            logger.error(f"Error scraping FreshersWorld: {e}")
            
        logger.info(f"Scraped {len(jobs)} jobs from fresher-specific job sites")
        return jobs
    except Exception as e:
        logger.error(f"Error in scrape_fresher_job_sites: {e}")
        return []

# Function to update job sources every minute (one source per minute)
# This prevents hitting all sources at once and getting rate-limited
async def check_job_source(source_name):
    logger.info(f"Checking job source: {source_name}")
    jobs = []
    
    if source_name == "indeed":
        jobs = await scrape_indeed()
    elif source_name == "linkedin":
        jobs = await scrape_linkedin()
    elif source_name == "remoteok":
        jobs = await scrape_remoteok()
    elif source_name == "stackoverflow":
        jobs = await scrape_stackoverflow()
    elif source_name == "fresher_sites":
        jobs = await scrape_fresher_job_sites()
    elif source_name == "google":
        if GOOGLE_API_KEY and GOOGLE_CSE_ID:
            jobs = search_google_jobs()
            
    if jobs:
        await send_jobs_to_users(jobs)
        
def rotate_job_sources():
    # List of sources to check one at a time
    sources = ["indeed", "linkedin", "remoteok", "stackoverflow", "fresher_sites", "google"]
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
        
        # Filter to only include target roles and new jobs
        new_jobs = []
        for job_title, link in jobs:
            if is_target_job(job_title):
                unique_id = f"{job_title}_{link}"
                if unique_id not in sent_jobs:
                    sent_jobs.add(unique_id)
                    # Clean job title of any special characters that might break Markdown
                    job_title = job_title.replace("*", "").replace("_", "").replace("`", "").replace("[", "").replace("]", "")
                    new_jobs.append((job_title, link))
        
        if not new_jobs:
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
        logger.error(f"Error in send_jobs_to_users: {e}")

def start_scheduler(app):
    global scheduler
    
    if scheduler:
        scheduler.shutdown(wait=False)
    
    scheduler = BackgroundScheduler()
    get_next_source = rotate_job_sources()

    # Function that runs every minute to check one job source at a time
    def check_next_source():
        source = get_next_source()
        asyncio.create_task(check_job_source(source))

    # Run every minute
    scheduler.add_job(check_next_source, 'interval', minutes=1)
    scheduler.start()
    logger.info("Scheduler started - checking one job source every minute...")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Subscribe a user when they use the /start command."""
    user_id = update.effective_chat.id
    
    if user_id not in subscribed_users:
        subscribed_users.add(user_id)
        save_users()
        await update.message.reply_text(
            'Welcome to the Entry-Level IT Job Alert Bot! 🚀\n\n'
            'You will now receive entry-level IT job updates for developers, data analysts, testers, '
            'cybersecurity, and UI/UX designer roles every minute.\n\n'
            'Type /help to see all available commands.'
        )
    else:
        await update.message.reply_text(
            'You are already subscribed to job alerts! 📝\n'
            'You will continue to receive entry-level IT job updates every minute.'
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
*Entry-Level IT Job Alert Bot - Commands*

/start - Subscribe to job alerts
/stop - Unsubscribe from job alerts
/help - Show this help message
/jobs - Check for new jobs now
/status - Check bot status and subscription info
/roles - Show job roles we're tracking

The bot automatically checks for new entry-level IT jobs every minute and sends them directly to you.

We focus on fresher/entry-level roles in:
• Software Development
• Data Analysis
• QA Testing
• Cybersecurity
• UI/UX Design

Job sources include: Indeed, LinkedIn, RemoteOK, StackOverflow, Google Jobs, Internshala, and FreshersWorld.
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def roles_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the job roles that the bot is tracking."""
    roles_text = """
*Job Roles We're Tracking:*

*👨‍💻 Developer Roles:*
• Junior Developer
• Entry-level Developer
• Fresher Developer
• Graduate Developer
• Web Developer (Frontend/Backend)

*📊 Data Roles:*
• Junior Data Analyst
• Entry-level Data Analyst
• Business Analyst
• Junior Data Scientist

*🧪 Testing Roles:*
• Software Tester
• QA Engineer
• Test Engineer
• Junior QA

*🔒 Security Roles:*
• Junior Security Analyst
• Entry-level Cybersecurity
• Information Security

*🎨 Design Roles:*
• UI Designer
• UX Designer
• UI/UX Designer
• Junior Product Designer

All roles are focused on fresher, entry-level, junior, graduate, and trainee positions.
    """
    await update.message.reply_text(roles_text, parse_mode='Markdown')

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
Update frequency: Every minute (one source at a time)
Focus: Entry-level IT jobs (Developers, Data, Testing, Security, UI/UX)
    """
    await update.message.reply_text(stats, parse_mode='Markdown')

async def force_job_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Force a job check when /jobs command is issued."""
    user_id = update.effective_chat.id
    
    if user_id not in subscribed_users:
        await update.message.reply_text('You need to subscribe first. Use /start to subscribe to job alerts.')
        return
        
    await update.message.reply_text('Checking for fresh entry-level IT jobs...')
    
    # Perform a special check for just this user
    try:
        bot = Bot(BOT_TOKEN)
        
        # Collect jobs from all sources (using await for async functions)
        all_jobs = []
        all_jobs.extend(await scrape_indeed())
        all_jobs.extend(await scrape_linkedin())
        all_jobs.extend(await scrape_remoteok())
        all_jobs.extend(await scrape_stackoverflow())
        all_jobs.extend(await scrape_fresher_job_sites())
        
        # Add Google jobs if API credentials are available
        if GOOGLE_API_KEY and GOOGLE_CSE_ID:
            all_jobs.extend(search_google_jobs())
        
        # Filter for target roles only
        filtered_jobs = [(title, link) for title, link in all_jobs if is_target_job(title)]
        
        # Get all relevant jobs, not just 10
        jobs_to_send = filtered_jobs
        
        # Send all filtered jobs to this specific user
        jobs_sent = 0
        
        for job_title, link in jobs_to_send:
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
            await update.message.reply_text(f'Sent you {jobs_sent} recent entry-level IT job listings!')
        else:
            await update.message.reply_text('No new entry-level IT jobs found at the moment. Check back later!')
            
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
    app.add_handler(CommandHandler("roles", roles_command))
    
    # Start the scheduler
    start_scheduler(app)
    
    # Run the bot
    logger.info(f"Bot started and polling with {len(subscribed_users)} subscribed users")
    await app.run_polling()

if __name__ == "__main__":
    logger.info("Entry-Level IT Jobs Bot is starting...")
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