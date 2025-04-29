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

# File to store user data and job history
USERS_FILE = "users.json"
JOB_HISTORY_FILE = "job_history.json"

# Global variables
job_history = {}  # Store job history with timestamps
scheduler = None
subscribed_users = set()
MAX_JOBS_HISTORY = 5000  # Limit job history size to prevent memory issues

# Define recency threshold - only consider jobs from the last 7 days
RECENCY_THRESHOLD_DAYS = 7

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

# Load job history from file
def load_job_history():
    global job_history
    try:
        if os.path.exists(JOB_HISTORY_FILE):
            with open(JOB_HISTORY_FILE, 'r') as f:
                job_history = json.load(f)
                logger.info(f"Loaded {len(job_history)} job history entries")
                
                # Clean up old entries to prevent file growth
                now = datetime.now()
                cutoff_date = (now - timedelta(days=RECENCY_THRESHOLD_DAYS)).timestamp()
                
                # Remove jobs older than the cutoff date
                old_jobs = [job_id for job_id, timestamp in job_history.items() if timestamp < cutoff_date]
                for job_id in old_jobs:
                    del job_history[job_id]
                
                logger.info(f"Removed {len(old_jobs)} old job entries, {len(job_history)} remain")
    except Exception as e:
        logger.error(f"Error loading job history: {e}")
        job_history = {}

# Save job history to file
def save_job_history():
    try:
        # Limit size if too large
        if len(job_history) > MAX_JOBS_HISTORY:
            # Keep only the newest entries
            sorted_jobs = sorted(job_history.items(), key=lambda x: x[1], reverse=True)
            job_history.clear()
            for job_id, timestamp in sorted_jobs[:MAX_JOBS_HISTORY]:
                job_history[job_id] = timestamp
        
        with open(JOB_HISTORY_FILE, 'w') as f:
            json.dump(job_history, f)
        logger.info(f"Saved {len(job_history)} job history entries")
    except Exception as e:
        logger.error(f"Error saving job history: {e}")

# Check if a job matches target roles
def is_target_job(job_title):
    job_title_lower = job_title.lower()
    # Check if any target role is in the job title
    return any(role in job_title_lower for role in TARGET_ROLES)

# Check if a job is recent (posted within RECENCY_THRESHOLD_DAYS)
def is_recent_job(job_id, job_date=None):
    # If we already have this job in history, check its timestamp
    if job_id in job_history:
        job_timestamp = job_history[job_id]
        cutoff_timestamp = (datetime.now() - timedelta(days=RECENCY_THRESHOLD_DAYS)).timestamp()
        return job_timestamp >= cutoff_timestamp
    
    # If we have a job date string, try to parse it
    if job_date:
        try:
            # Try to parse various date formats
            date_patterns = [
                r'(\d{1,2}\s+\w+\s+\d{4})',  # 15 April 2023
                r'(\d{1,2}\s+\w+)',  # 15 April
                r'(\w+\s+\d{1,2})',  # April 15
                r'(\d{1,2}/\d{1,2}/\d{2,4})',  # 04/15/2023
                r'(\d{1,2}-\d{1,2}-\d{2,4})',  # 04-15-2023
                r'(today|yesterday|just now|\d+\s+(?:hour|hr|day|week)s?\s+ago)'  # Relative time
            ]
            
            found_date = None
            for pattern in date_patterns:
                match = re.search(pattern, job_date.lower())
                if match:
                    found_date = match.group(1)
                    break
            
            if found_date:
                now = datetime.now()
                
                # Handle relative dates
                if "just now" in found_date or "hour" in found_date or "hr" in found_date:
                    return True  # Very recent
                elif "today" in found_date:
                    return True
                elif "yesterday" in found_date:
                    return True
                elif "day" in found_date and "ago" in found_date:
                    try:
                        days = int(re.search(r'(\d+)', found_date).group(1))
                        return days <= RECENCY_THRESHOLD_DAYS
                    except:
                        return True  # If we can't parse, assume it's recent
                elif "week" in found_date and "ago" in found_date:
                    try:
                        weeks = int(re.search(r'(\d+)', found_date).group(1))
                        return weeks <= RECENCY_THRESHOLD_DAYS // 7
                    except:
                        return True
                
                # If we found a date but couldn't parse it as relative, assume it's recent
                return True
        except Exception as e:
            logger.warning(f"Error parsing job date '{job_date}': {e}")
    
    # By default, consider a new job as recent
    # Record timestamp for future reference
    job_history[job_id] = datetime.now().timestamp()
    return True

# Google Custom Search API for targeted entry-level jobs
def search_google_jobs():
    try:
        if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
            logger.warning("Google API credentials not set, skipping Google job search")
            return []
            
        service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
        date_str = datetime.now().strftime("%Y-%m-%d")
        jobs = []
        
        # Search with date restrictions for recent jobs
        search_queries = [
            "developer fresher", "data analyst entry level", 
            "software tester junior", "cybersecurity entry level", 
            "ui ux designer junior"
        ]
        
        for role in search_queries:
            try:
                result = service.cse().list(
                    q=f"{role} jobs posted last {RECENCY_THRESHOLD_DAYS} days",
                    cx=GOOGLE_CSE_ID,
                    num=5,  # Get fewer results per role but more variety
                    dateRestrict=f"d{RECENCY_THRESHOLD_DAYS}"  # Last N days
                ).execute()
                
                if "items" in result:
                    for item in result["items"]:
                        title = item["title"]
                        link = item["link"]
                        snippet = item.get("snippet", "")
                        
                        # Extract date from snippet if possible
                        job_date = None
                        date_match = re.search(r'(\d{1,2}\s+\w+\s+\d{4}|\d{1,2}\s+\w+|\w+\s+\d{1,2}|today|yesterday|\d+\s+days?\s+ago)', snippet, re.IGNORECASE)
                        if date_match:
                            job_date = date_match.group(1)
                        
                        # Only add jobs that match our target criteria and are recent
                        job_id = f"google_{title}_{link}"
                        if is_target_job(title) and is_recent_job(job_id, job_date):
                            jobs.append((title, link, job_date))
                            
                # Add a small delay between API calls
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
        
        # Search for multiple job types with fresher/entry-level focus and date filter
        search_terms = [
            "entry+level+developer", "junior+developer", "fresher+developer",
            "entry+level+data+analyst", "junior+data+analyst",
            "entry+level+tester", "junior+qa",
            "entry+level+cybersecurity", "junior+security+analyst",
            "junior+ui+ux+designer", "entry+level+ui+designer"
        ]
        
        for term in search_terms[:3]:  # Limit to avoid too many requests
            try:
                # Add date filter to get only recent jobs
                url = f"https://www.indeed.com/jobs?q={term}&sort=date&fromage={RECENCY_THRESHOLD_DAYS}"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9"
                }
                response = requests.get(url, headers=headers, timeout=15)
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Try multiple possible selectors for Indeed's layout
                job_cards = soup.select("div.job_seen_beacon") or soup.select("div.tapItem") or soup.select("div[class*='job_']")
                
                for card in job_cards:
                    try:
                        # Extract job title
                        title_elem = card.select_one("h2.jobTitle") or card.select_one("h2.title") or card.select_one("span[title]") or card.select_one("a[data-jk]")
                        if title_elem:
                            title = title_elem.get_text(strip=True)
                            
                            # Extract link
                            link_elem = title_elem if title_elem.name == "a" else title_elem.find("a")
                            link = ""
                            job_id = ""
                            
                            if link_elem and link_elem.has_attr('href'):
                                href = link_elem.get('href')
                                job_id = link_elem.get('data-jk') or link_elem.get('id', '').replace('job_', '')
                                
                                if not job_id and 'jk=' in href:
                                    job_id = re.search(r'jk=([^&]+)', href).group(1)
                                    
                                if job_id:
                                    link = f"https://www.indeed.com/viewjob?jk={job_id}"
                                elif href.startswith('/'):
                                    link = f"https://www.indeed.com{href}"
                                else:
                                    link = href
                            
                            # Extract date
                            date_elem = card.select_one("span.date") or card.select_one("span[class*='date']") or card.select_one("div[class*='date']")
                            job_date = date_elem.get_text(strip=True) if date_elem else None
                            
                            # Only add if it matches our target criteria and is recent
                            unique_id = f"indeed_{job_id or title}_{link}"
                            if is_target_job(title) and is_recent_job(unique_id, job_date):
                                jobs.append((title, link, job_date))
                    except Exception as card_error:
                        logger.error(f"Error processing Indeed job card: {card_error}")
                        continue
                
                # Add a delay between requests to avoid rate limiting
                await asyncio.sleep(1)
            except Exception as term_error:
                logger.error(f"Error scraping Indeed for term {term}: {term_error}")
                continue
        
        logger.info(f"Scraped {len(jobs)} recent fresher jobs from Indeed")
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
                # f_TPR=r86400 - last 24 hours, f_TPR=r604800 - last week
                url = f"https://www.linkedin.com/jobs/search/?keywords={term}&f_E=2&f_TPR=r{RECENCY_THRESHOLD_DAYS * 86400}&sortBy=DD"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9"
                }
                response = requests.get(url, headers=headers, timeout=15)
                soup = BeautifulSoup(response.text, "html.parser")
                
                job_cards = soup.select("div.base-card") or soup.select("li.job-search-card")
                for card in job_cards:
                    try:
                        title_elem = card.select_one("h3.base-search-card__title") or card.select_one("h3.job-search-card__title")
                        link_elem = card.select_one("a.base-card__full-link") or card.select_one("a.job-search-card__link")
                        date_elem = card.select_one("time") or card.select_one("div.job-search-card__listdate") or card.select_one("span.job-search-card__listdate")
                        
                        if title_elem and link_elem:
                            title = title_elem.get_text(strip=True)
                            link = link_elem.get('href', '').split('?')[0]  # Remove query params
                            
                            # Extract date information
                            job_date = None
                            if date_elem:
                                if date_elem.has_attr('datetime'):
                                    job_date = date_elem['datetime']
                                else:
                                    job_date = date_elem.get_text(strip=True)
                            
                            # Only add recent jobs that match our target criteria
                            job_id = f"linkedin_{title}_{link}"
                            if title and link and is_target_job(title) and is_recent_job(job_id, job_date):
                                jobs.append((title, link, job_date))
                    except Exception as card_error:
                        logger.error(f"Error processing LinkedIn job card: {card_error}")
                        continue
                
                # Add a delay between requests
                await asyncio.sleep(1)
            except Exception as term_error:
                logger.error(f"Error scraping LinkedIn for term {term}: {term_error}")
                continue
                    
        logger.info(f"Scraped {len(jobs)} recent entry-level jobs from LinkedIn")
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
                            
                            # Extract date information
                            date_tag = tr.find('td', class_='time') or tr.find('time')
                            job_date = date_tag.get_text(strip=True) if date_tag else None
                            
                            if title_tag:
                                job_title = title_tag.get_text(strip=True)
                                # Only add if relevant to our target roles and recent
                                job_id = f"remoteok_{job_title}_{link}"
                                if is_target_job(job_title) and is_recent_job(job_id, job_date):
                                    jobs.append((job_title, link, job_date))
                    except Exception as job_error:
                        logger.error(f"Error processing RemoteOK job: {job_error}")
                        continue
                
                # Add a delay between requests
                await asyncio.sleep(1)
            except Exception as term_error:
                logger.error(f"Error scraping RemoteOK for term {term}: {term_error}")
                continue
                
        logger.info(f"Scraped {len(jobs)} recent entry-level jobs from RemoteOK")
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
                # Add age filter for recent jobs
                url = f"https://stackoverflow.com/jobs?q={term.replace(' ', '+')}&sort=p"  # Sort by publication date
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                response = requests.get(url, headers=headers, timeout=15)
                soup = BeautifulSoup(response.text, "html.parser")
                
                for div in soup.select("div.listResults div.-job"):
                    try:
                        title_elem = div.select_one("h2 a")
                        date_elem = div.select_one("span.fc-danger") or div.select_one("span.-posted-date")
                        
                        if title_elem:
                            title = title_elem.get_text(strip=True)
                            link = f"https://stackoverflow.com{title_elem['href']}"
                            
                            # Extract date
                            job_date = date_elem.get_text(strip=True) if date_elem else None
                            
                            # Only add if it's a target job and recent
                            job_id = f"stackoverflow_{title}_{link}"
                            if is_target_job(title) and is_recent_job(job_id, job_date):
                                jobs.append((title, link, job_date))
                    except Exception as job_error:
                        logger.error(f"Error processing StackOverflow job: {job_error}")
                        continue
                
                # Add delay between requests
                await asyncio.sleep(1)
            except Exception as term_error:
                logger.error(f"Error scraping StackOverflow for term {term}: {term_error}")
                continue
                
        logger.info(f"Scraped {len(jobs)} recent fresher jobs from StackOverflow")
        return jobs
    except Exception as e:
        logger.error(f"Error scraping StackOverflow: {e}")
        return []

# Scrape fresher-specific job sites
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
                    try:
                        title_elem = container.select_one("a.view_detail_button")
                        date_elem = container.select_one(".status-container") or container.select_one(".posted")
                        
                        if title_elem:
                            company_elem = container.select_one(".company_name")
                            company = company_elem.get_text(strip=True) if company_elem else "Company"
                            title = f"{title_elem.get_text(strip=True)} at {company}"
                            link = "https://internshala.com" + title_elem.get('href', '')
                            
                            # Extract date
                            job_date = date_elem.get_text(strip=True) if date_elem else None
                            
                            # Only add recent jobs
                            job_id = f"internshala_{title}_{link}"
                            if is_recent_job(job_id, job_date):
                                jobs.append((title, link, job_date))
                    except Exception as job_error:
                        logger.error(f"Error processing Internshala job: {job_error}")
                        continue
                
                await asyncio.sleep(1)  # Delay between requests
        except Exception as e:
            logger.error(f"Error scraping Internshala: {e}")
            
        # Freshersworld (specialized in fresher jobs)
        try:
            fresher_roles = ["software-developer", "data-analyst", "software-tester", 
                             "cyber-security", "ui-designer"]
            for role in fresher_roles[:2]:  # Limit to 2 roles
                url = f"https://www.freshersworld.com/jobs/search?job={role}&limit=50&sort=date"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                response = requests.get(url, headers=headers, timeout=15)
                soup = BeautifulSoup(response.text, "html.parser")
                
                job_listings = soup.select(".job-container")
                for job in job_listings:
                    try:
                        title_elem = job.select_one(".job-title")
                        company_elem = job.select_one(".job-company")
                        link_elem = job.select_one("a")
                        date_elem = job.select_one(".job-date") or job.select_one(".posted-date")
                        
                        if title_elem and link_elem:
                            company = company_elem.get_text(strip=True) if company_elem else "Company"
                            title = f"{title_elem.get_text(strip=True)} - {company}"
                            link = link_elem.get('href', '')
                            if not link.startswith('http'):
                                link = "https://www.freshersworld.com" + link
                            
                            # Extract date
                            job_date = date_elem.get_text(strip=True) if date_elem else None
                            
                            # Only add recent jobs
                            job_id = f"freshersworld_{title}_{link}"
                            if is_recent_job(job_id, job_date):
                                jobs.append((title, link, job_date))
                    except Exception as job_error:
                        logger.error(f"Error processing FreshersWorld job: {job_error}")
                        continue
                
                await asyncio.sleep(1)  # Delay between requests
        except Exception as e:
            logger.error(f"Error scraping FreshersWorld: {e}")
            
        logger.info(f"Scraped {len(jobs)} recent jobs from fresher-specific job sites")
        return jobs
    except Exception as e:
        logger.error(f"Error in scrape_fresher_job_sites: {e}")
        return []

# Function to check job source and send updates
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

# Rotate through job sources
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

# Send jobs to subscribed users
async def send_jobs_to_users(jobs):
    try:
        if not subscribed_users or not jobs:
            return
            
        bot = Bot(BOT_TOKEN)
        
        # Filter for new jobs only
        new_jobs = []
        now = datetime.now()
        
        for job_title, link, job_date in jobs:
            unique_id = f"{job_title}_{link}"
            
            # Only consider jobs that haven't been sent before or are very recent
            if unique_id not in job_history:
                # Record this job with current timestamp
                job_history[unique_id] = now.timestamp()
                
                # Clean job title of any special characters that might break Markdown
                job_title = job_title.replace("*", "").replace("_", "").replace("`", "").replace("[", "").replace("]", "")
                new_jobs.append((job_title, link, job_date))
        
        if not new_jobs:
            return
            
        logger.info(f"Sending {len(new_jobs)} new jobs to {len(subscribed_users)} users")
        
        # Save updated job history
        save_job_history()
        
        # Send each new job to all subscribed users
        for user_id in list(subscribed_users):  # Create a copy of the list to safely modify during iteration
            try:
                jobs_sent = 0
                for job_title, link, job_date in new_jobs:
                    # Format date information for display if available
                    date_info = f"⏰ Posted: {job_date}" if job_date else f"⏰ Posted recently"
                    
                    message = f"💼 *{job_title}*\n🔗 [Apply Here]({link})\n{date_info}"
                    try:
                        # Continuing from where your code was cut off...

                        await bot.send_message(
                            chat_id=user_id,
                            text=message,
                            parse_mode='Markdown',
                            disable_web_page_preview=False
                        )
                        jobs_sent += 1
                        
                        # Add a small delay between messages to avoid hitting rate limits
                        await asyncio.sleep(0.5)
                        
                        # Limit to at most 5 jobs per notification batch to avoid spam
                        if jobs_sent >= 5:
                            break
                            
                    except Exception as msg_error:
                        logger.error(f"Error sending message to user {user_id}: {msg_error}")
                        continue
                        
                # Send a batch summary message if multiple jobs were sent
                if jobs_sent > 0:
                    try:
                        summary = f"✅ Sent you {jobs_sent} new fresher job opportunities!"
                        if jobs_sent == 5 and len(new_jobs) > 5:
                            summary += f"\n\nThere are {len(new_jobs) - 5} more jobs available. Stay tuned for the next update!"
                        
                        await bot.send_message(
                            chat_id=user_id,
                            text=summary
                        )
                    except Exception as summary_error:
                        logger.error(f"Error sending summary to user {user_id}: {summary_error}")
                
            except Exception as user_error:
                logger.error(f"Error processing user {user_id}: {user_error}")
                # If we get a chat not found/blocked error, remove the user from subscribed list
                if "bot was blocked by the user" in str(user_error) or "chat not found" in str(user_error):
                    subscribed_users.discard(user_id)
                    logger.info(f"Removed user {user_id} from subscription list")
                    save_users()
    except Exception as e:
        logger.error(f"Error in send_jobs_to_users: {e}")

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_chat.id
        await context.bot.send_message(
            chat_id=user_id,
            text="🚀 Welcome to the Fresher Job Alert Bot! 🚀\n\n"
                 "I'll send you the latest entry-level job opportunities in tech.\n\n"
                 "Commands:\n"
                 "/subscribe - Start receiving job alerts\n"
                 "/unsubscribe - Stop receiving job alerts\n"
                 "/help - Show this help message\n"
                 "/check - Check for jobs right now"
        )
    except Exception as e:
        logger.error(f"Error in start command: {e}")

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_chat.id
        if user_id in subscribed_users:
            await context.bot.send_message(
                chat_id=user_id,
                text="✅ You are already subscribed to job alerts!"
            )
        else:
            subscribed_users.add(user_id)
            save_users()
            await context.bot.send_message(
                chat_id=user_id,
                text="✅ You have successfully subscribed to job alerts! You'll receive updates for new fresher job opportunities."
            )
    except Exception as e:
        logger.error(f"Error in subscribe command: {e}")

async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_chat.id
        if user_id in subscribed_users:
            subscribed_users.discard(user_id)
            save_users()
            await context.bot.send_message(
                chat_id=user_id,
                text="✅ You have unsubscribed from job alerts. You will no longer receive updates."
            )
        else:
            await context.bot.send_message(
                chat_id=user_id,
                text="❓ You are not currently subscribed to job alerts."
            )
    except Exception as e:
        logger.error(f"Error in unsubscribe command: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_chat.id
        await context.bot.send_message(
            chat_id=user_id,
            text="🔍 *Fresher Job Alert Bot Help* 🔍\n\n"
                 "This bot sends you the latest entry-level tech job opportunities.\n\n"
                 "*Commands:*\n"
                 "/subscribe - Start receiving job alerts\n"
                 "/unsubscribe - Stop receiving job alerts\n"
                 "/help - Show this help message\n"
                 "/check - Check for jobs right now\n\n"
                 "The bot checks for new jobs every few minutes and will notify you when fresh opportunities are found.",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in help command: {e}")

async def check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_chat.id
        await context.bot.send_message(
            chat_id=user_id,
            text="🔍 Checking for new job opportunities now... This may take a moment."
        )
        
        # Get the next source in rotation
        source = next_source()
        
        # Run a job check immediately for this user
        await check_job_source(source)
        
        # Send confirmation even if no new jobs were found
        await context.bot.send_message(
            chat_id=user_id,
            text="✅ Job check completed! If any new opportunities were found, they have been sent to you."
        )
    except Exception as e:
        logger.error(f"Error in check_now command: {e}")
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Sorry, there was an error checking for jobs. Please try again later."
        )

# Modified function to check a job source on a schedule
async def scheduled_job_check():
    try:
        # Get the next source to check
        source = next_source()
        logger.info(f"Running scheduled job check for source: {source}")
        await check_job_source(source)
    except Exception as e:
        logger.error(f"Error in scheduled job check: {e}")


# Main function to set up the bot
async def main():
    global scheduler, next_source
    
    # Load users and job history
    load_users()
    load_job_history()
    
    # Create rotator for job sources
    next_source = rotate_job_sources()
    
    # Start scheduler
    scheduler = BackgroundScheduler()
    
    # Schedule job checks every minute
    scheduler.add_job(
        lambda: asyncio.create_task(scheduled_job_check()),
        'interval',
        minutes=1,  # Check every minute for more frequent updates
        id='job_check'
    )
    
    # Schedule a daily cleanup of old job history entries
    scheduler.add_job(
        lambda: (load_job_history(), save_job_history()),
        'cron',
        hour=0,
        minute=0,
        id='cleanup'
    )
    
    scheduler.start()
    logger.info("Scheduler started")
    
    # Initialize the bot
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("subscribe", subscribe))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("check", check_now))
    
    # Start the bot - using the correct method for newer python-telegram-bot versions
    await application.initialize()
    await application.start()
    logger.info("Bot started polling")
    
    # Run until user interrupts with Ctrl+C
    await application.updater.start_polling()
    await application.idle()

# Entry point
if __name__ == "__main__":
    try:
        # Improve job recency filtering
        RECENCY_THRESHOLD_DAYS = 7  # Only consider jobs from the last 7 days
        
        # Run the main function
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        # Shutdown the scheduler if it's running
        if scheduler and scheduler.running:
            scheduler.shutdown()
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)  # Added exc_info=True for better error logs
        # Ensure scheduler is shutdown
        if scheduler and scheduler.running:
            scheduler.shutdown()