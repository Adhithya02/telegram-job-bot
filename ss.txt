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
sent_jobs = set()
scheduler = None
subscribed_users = set()

# Define fresher job time window (in days)
JOB_MAX_AGE_DAYS = 7  # Only consider jobs posted within the last week

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

# Month name to number for date parsing
MONTH_MAP = {
    'jan': 1, 'january': 1,
    'feb': 2, 'february': 2, 
    'mar': 3, 'march': 3,
    'apr': 4, 'april': 4,
    'may': 5, 'may': 5,
    'jun': 6, 'june': 6,
    'jul': 7, 'july': 7,
    'aug': 8, 'august': 8,
    'sep': 9, 'september': 9, 
    'oct': 10, 'october': 10,
    'nov': 11, 'november': 11,
    'dec': 12, 'december': 12
}

# Common date patterns in job listings
DATE_PATTERNS = [
    r'posted\s+(\d+)\s*(day|days|hr|hrs|hour|hours|min|mins|minute|minutes)\s+ago',
    r'(\d+)\s*(day|days|hr|hrs|hour|hours|min|mins|minute|minutes)\s+ago',
    r'posted\s+(today|yesterday)',
    r'(today|yesterday)',
    r'posted\s+on\s+(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})',
    r'posted\s+on\s+(\w+)\s+(\d{1,2}),?\s+(\d{4})',
    r'posted\s+(\w+)\s+(\d{1,2}),?\s+(\d{4})',
    r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})',
    r'(\w+)\s+(\d{1,2}),?\s+(\d{4})'
]

# Function to parse dates from text
def parse_date_from_text(text):
    if not text:
        return None
    
    text = text.lower().strip()
    now = datetime.now()
    
    # Try each pattern
    for pattern in DATE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            groups = match.groups()
            
            # Handle "today" or "yesterday"
            if 'today' in groups:
                return now.date()
            elif 'yesterday' in groups:
                return (now - timedelta(days=1)).date()
            
            # Handle "X days/hours/minutes ago"
            if len(groups) >= 2 and groups[0].isdigit():
                time_value = int(groups[0])
                time_unit = groups[1].lower()
                
                if 'day' in time_unit:
                    return (now - timedelta(days=time_value)).date()
                elif 'hour' in time_unit or 'hr' in time_unit:
                    return (now - timedelta(hours=time_value)).date()
                elif 'min' in time_unit:
                    return now.date()  # Posted today
            
            # Handle MM/DD/YYYY format
            if len(groups) == 3 and all(g.isdigit() for g in groups):
                month, day, year = int(groups[0]), int(groups[1]), int(groups[2])
                if year < 100:  # Handle 2-digit years
                    year += 2000
                try:
                    return datetime(year, month, day).date()
                except ValueError:
                    pass  # Invalid date, try next pattern
            
            # Handle "Month DD, YYYY" format
            if len(groups) == 3 and groups[0].isalpha() and groups[1].isdigit() and groups[2].isdigit():
                month_name = groups[0].lower()
                day = int(groups[1])
                year = int(groups[2])
                
                if month_name in MONTH_MAP:
                    month = MONTH_MAP[month_name]
                    try:
                        return datetime(year, month, day).date()
                    except ValueError:
                        pass  # Invalid date, try next pattern
    
    # No valid date found
    return None

# Check if a job is recent (within JOB_MAX_AGE_DAYS)
def is_recent_job(job_date):
    if not job_date:
        # If we can't determine date, assume it's recent
        # This is more risky, but we'll modify this to be strict
        return False  
        
    now = datetime.now().date()
    date_threshold = now - timedelta(days=JOB_MAX_AGE_DAYS)
    
    return job_date >= date_threshold

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
    global sent_jobs
    try:
        if os.path.exists(JOB_HISTORY_FILE):
            with open(JOB_HISTORY_FILE, 'r') as f:
                job_data = json.load(f)
                sent_jobs = set(job_data.get('jobs', []))
                logger.info(f"Loaded {len(sent_jobs)} job history entries")
                
                # Trim job history if it gets too large (keep most recent 5000)
                if len(sent_jobs) > 5000:
                    sent_jobs = set(list(sent_jobs)[-5000:])
    except Exception as e:
        logger.error(f"Error loading job history: {e}")
        sent_jobs = set()

# Save job history to file
def save_job_history():
    try:
        with open(JOB_HISTORY_FILE, 'w') as f:
            json.dump({'jobs': list(sent_jobs)}, f)
        logger.info(f"Saved {len(sent_jobs)} job history entries")
    except Exception as e:
        logger.error(f"Error saving job history: {e}")

# Check if a job matches target roles
def is_target_job(job_title):
    if not job_title:
        return False
        
    job_title_lower = job_title.lower()
    # Check if any target role is in the job title
    return any(role in job_title_lower for role in TARGET_ROLES)

# Clean and normalize job title to avoid duplicates with slightly different formatting
def normalize_job_title(title):
    if not title:
        return ""
    # Remove extra spaces, lowercase, and strip punctuation
    title = re.sub(r'\s+', ' ', title.lower().strip())
    title = re.sub(r'[^\w\s]', '', title)
    return title

# Google Custom Search API for targeted entry-level jobs
def search_google_jobs():
    try:
        if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
            logger.warning("Google API credentials not set, skipping Google job search")
            return []
            
        service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
        
        # Get today's date for fresh results
        today = datetime.now().strftime("%Y-%m-%d")
        one_week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        jobs = []
        
        # Search for each target role separately with date filters
        for role in ["developer fresher", "data analyst entry level", "software tester junior", 
                    "cybersecurity entry level", "ui ux designer junior"]:
            try:
                # Add date range to query to get more recent results
                result = service.cse().list(
                    q=f"{role} jobs posted after:{one_week_ago}",
                    cx=GOOGLE_CSE_ID,
                    num=10,  # Get more results per query
                    sort="date",  # Sort by date
                    dateRestrict="w1"  # Last week
                ).execute()
                
                if "items" in result:
                    for item in result["items"]:
                        title = item.get("title", "")
                        link = item.get("link", "")
                        snippet = item.get("snippet", "")
                        
                        # Extract date from snippet if possible
                        job_date = parse_date_from_text(snippet)
                        
                        # Only add jobs that match our target criteria and are recent
                        if is_target_job(title) and (job_date is None or is_recent_job(job_date)):
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
        
        # Search for multiple job types with fresher/entry-level focus and date filters
        search_terms = [
            "entry+level+developer", "junior+developer", "fresher+developer",
            "entry+level+data+analyst", "junior+data+analyst",
            "entry+level+tester", "junior+qa",
            "entry+level+cybersecurity", "junior+security+analyst",
            "junior+ui+ux+designer", "entry+level+ui+designer"
        ]
        
        for term in search_terms[:3]:  # Limit to avoid too many requests
            try:
                # Add date filter for last 7 days - IMPORTANT for getting recent jobs
                url = f"https://www.indeed.com/jobs?q={term}&sort=date&fromage=7"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9"
                }
                response = requests.get(url, headers=headers, timeout=15)
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Try multiple possible selectors for Indeed's layout
                job_cards = soup.select("div.job_seen_beacon") or soup.select("div.tapItem")
                
                for card in job_cards:
                    # Get job title
                    title_elem = card.select_one("h2.jobTitle") or card.select_one("h2.title")
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        link_elem = title_elem.find("a")
                        if link_elem and link_elem.has_attr('href'):
                            job_id = link_elem.get('data-jk') or link_elem.get('id', '').replace('job_', '')
                            if job_id:
                                link = f"https://www.indeed.com/viewjob?jk={job_id}"
                                
                                # Try to extract date info
                                date_elem = card.select_one("span.date") or card.select_one(".date")
                                date_text = date_elem.get_text(strip=True) if date_elem else None
                                job_date = parse_date_from_text(date_text)
                                
                                # For Indeed, assume jobs are recent if no date (because of our search parameters)
                                if job_date is None:
                                    job_date = datetime.now().date()
                                
                                # Only add if it matches our target criteria and is recent
                                if is_target_job(title) and is_recent_job(job_date):
                                    jobs.append((title, link, job_date))
                
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
        
        # Search for multiple job types with entry-level focus and date filters
        search_terms = [
            "entry-level-developer", "junior-data-analyst", 
            "entry-level-tester", "entry-level-cybersecurity", 
            "junior-ui-ux-designer"
        ]
        
        for term in search_terms[:3]:  # Limit to avoid too many requests
            try:
                # Add date filter (f_TPR=r604800 is for last 7 days)
                url = f"https://www.linkedin.com/jobs/search/?keywords={term}&f_E=2&f_TPR=r604800&sortBy=DD"
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
                        
                        # Try to extract date info
                        date_elem = card.select_one("time") or card.select_one(".job-search-card__listdate")
                        date_text = date_elem.get_text(strip=True) if date_elem else None
                        job_date = parse_date_from_text(date_text)
                        
                        # For LinkedIn, assume jobs are recent if no date (because of our search parameters)
                        if job_date is None:
                            job_date = datetime.now().date()
                        
                        if title and link and is_target_job(title) and is_recent_job(job_date):
                            jobs.append((title, link, job_date))
                
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
                            if title_tag:
                                job_title = title_tag.get_text(strip=True)
                                
                                # Try to extract date info
                                date_tag = tr.find('time') or tr.find('td', class_='time')
                                date_text = date_tag.get_text(strip=True) if date_tag else None
                                job_date = parse_date_from_text(date_text)
                                
                                # For RemoteOK, we'll be stricter about date
                                if job_date is None:
                                    # Check for "new" tag as a hint for recency
                                    new_tag = tr.find('td', class_='new')
                                    if new_tag and "new" in new_tag.get_text(strip=True).lower():
                                        job_date = datetime.now().date()
                                
                                # Only add if relevant to our target roles and recent
                                if is_target_job(job_title) and (job_date and is_recent_job(job_date)):
                                    jobs.append((job_title, link, job_date))
                    except Exception as job_error:
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
        
        # Search for specific fresher/entry-level job categories with date filters
        search_terms = ["junior developer", "entry level data", "junior tester", 
                        "entry level security", "junior ui ux"]
        
        for term in search_terms[:2]:  # Limit to avoid too many requests
            try:
                # Add date filter (1 week)
                url = f"https://stackoverflow.com/jobs?q={term.replace(' ', '+')}&ms=junior&mxs=junior&sort=p"
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
                        
                        # Try to extract date info
                        date_elem = div.select_one("span.fc-black-500") or div.select_one(".date")
                        date_text = date_elem.get_text(strip=True) if date_elem else None
                        job_date = parse_date_from_text(date_text)
                        
                        # For StackOverflow, assume recent if sorting by newest and no date
                        if job_date is None:
                            job_date = datetime.now().date() - timedelta(days=3)  # Conservative estimate
                        
                        # Only add if it's a target job and recent
                        if is_target_job(title) and is_recent_job(job_date):
                            jobs.append((title, link, job_date))
                
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

# Function to scrape fresher-specific job sites with date filters
async def scrape_fresher_job_sites():
    try:
        jobs = []
        
        # Internshala (popular for freshers in some regions)
        try:
            internshala_roles = ["web-development", "data-science", "ui-ux-design", "cyber-security"]
            for role in internshala_roles[:2]:  # Limit to 2 roles to avoid too many requests
                # Add posting date filter
                url = f"https://internshala.com/internships/{role}/?utm_source=recent_jobs"
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
                        
                        # Try to extract date info
                        date_elem = container.select_one(".posted_by_container") or container.select_one(".posted")
                        date_text = date_elem.get_text(strip=True) if date_elem else None
                        job_date = parse_date_from_text(date_text)
                        
                        # For Internshala, most listings are recent given their model
                        if job_date is None:
                            job_date = datetime.now().date() - timedelta(days=5)  # Conservative estimate
                        
                        # Make sure it's recent
                        if is_recent_job(job_date):
                            jobs.append((title, link, job_date))
                
                await asyncio.sleep(1)  # Delay between requests
        except Exception as e:
            logger.error(f"Error scraping Internshala: {e}")
            
        # Freshersworld (specialized in fresher jobs)
        try:
            fresher_roles = ["software-developer", "data-analyst", "software-tester", 
                             "cyber-security", "ui-designer"]
            for role in fresher_roles[:2]:  # Limit to 2 roles
                # Add recent filter
                url = f"https://www.freshersworld.com/jobs/search?job={role}&sort=date&limit=10"
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
                        
                        # Try to extract date info
                        date_elem = job.select_one(".job-apply-date") or job.select_one(".job-date")
                        date_text = date_elem.get_text(strip=True) if date_elem else None
                        job_date = parse_date_from_text(date_text)
                        
                        # For FreshersWorld, assume recent if sorting by date and no date found
                        if job_date is None:
                            job_date = datetime.now().date() - timedelta(days=4)  # Conservative estimate
                        
                        # Make sure it's recent
                        if is_recent_job(job_date):
                            jobs.append((title, link, job_date))
                
                await asyncio.sleep(1)  # Delay between requests
        except Exception as e:
            logger.error(f"Error scraping FreshersWorld: {e}")
            
        logger.info(f"Scraped {len(jobs)} recent jobs from fresher-specific job sites")
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
        # Extract job tuples (title, link, date) into title and link only
        processed_jobs = [(title, link) for title, link, _ in jobs]
        await send_jobs_to_users(processed_jobs)
        
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
                # Normalize job title to avoid duplicates with slight differences
                normalized_title = normalize_job_title(job_title)
                unique_id = f"{normalized_title}_{link}"
                
                if unique_id not in sent_jobs:
                    sent_jobs.add(unique_id)
                    # Clean job title of any special characters that might break Markdown
                    clean_title = job_title.replace("*", "").replace("_", "").replace("`", "").replace("[", "").replace("]", "")
                    new_jobs.append((clean_title, link))
        
        if not new_jobs:
            return
            
        logger.info(f"Sending {len(new_jobs)} new jobs to {len(subscribed_users)} users")
        
        # Group jobs into batches to avoid sending too many messages at once
        # Send up to 10 jobs in one message
        grouped_jobs = []
        current_group = []
        
        for job_title, link in new_jobs:
            current_group.append((job_title, link))
            if len(current_group) >= 10:
                grouped_jobs.append(current_group)
                current_group = []
                
        if current_group:  # Add any remaining jobs
            grouped_jobs.append(current_group)
            
        # Send each group as a message to each subscribed user
        for user_id in subscribed_users:
            try:
                for job_group in grouped_jobs:
                    message = "🚨 *New Entry-Level Tech Jobs* 🚨\n\n"
                    for i, (job_title, link) in enumerate(job_group, 1):
                        message += f"{i}. [{job_title}]({link})\n\n"
                    
                    message += "\n_Use /stop to unsubscribe_"
                    
                    # Send with markdown formatting and disable web page preview
                    await bot.send_message(
                        chat_id=user_id,
                        text=message,
                        parse_mode="Markdown",
                        disable_web_page_preview=True
                    )
                    
                    # Add a small delay between messages to avoid hitting rate limits
                    await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Failed to send jobs to user {user_id}: {e}")
                
        # Save job history after successful sending
        save_job_history()
    except Exception as e:
        logger.error(f"Error sending jobs to users: {e}")

# Check for new jobs periodically
async def check_jobs():
    try:
        get_next_source = rotate_job_sources()
        
        while True:
            # Check one source at a time in rotation
            source_name = get_next_source()
            await check_job_source(source_name)
            
            # Save job history and users data periodically
            save_job_history()
            save_users()
            
            # Wait before checking the next source (1 minute rotation)
            await asyncio.sleep(60)
    except Exception as e:
        logger.error(f"Error in check_jobs loop: {e}")

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message when the command /start is issued."""
    try:
        user_id = update.effective_user.id
        subscribed_users.add(user_id)
        save_users()
        
        welcome_message = (
            "👋 *Welcome to the Entry-Level Job Alert Bot!* 👋\n\n"
            "I'll send you freshly posted entry-level tech job opportunities including:\n"
            "- Developer positions (frontend, backend, full-stack)\n"
            "- Data Analyst roles\n"
            "- QA Testers\n"
            "- Cybersecurity positions\n"
            "- UI/UX Designer jobs\n\n"
            "You're now subscribed! You'll receive notifications when new jobs match your profile.\n\n"
            "📝 *Available Commands:*\n"
            "/start - Start receiving job alerts\n"
            "/stop - Unsubscribe from job alerts\n"
            "/help - Show available commands"
        )
        
        await update.message.reply_text(welcome_message, parse_mode="Markdown")
        logger.info(f"User {user_id} subscribed to job alerts")
    except Exception as e:
        logger.error(f"Error in start command: {e}")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unsubscribes the user when the command /stop is issued."""
    try:
        user_id = update.effective_user.id
        if user_id in subscribed_users:
            subscribed_users.remove(user_id)
            save_users()
            
        await update.message.reply_text(
            "You've been unsubscribed from job alerts. "
            "Use /start to subscribe again anytime."
        )
        logger.info(f"User {user_id} unsubscribed from job alerts")
    except Exception as e:
        logger.error(f"Error in stop command: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends help info when the command /help is issued."""
    try:
        help_text = (
            "🤖 *Entry-Level Job Alert Bot Help* 🤖\n\n"
            "I send you fresh entry-level tech job opportunities.\n\n"
            "📝 *Available Commands:*\n"
            "/start - Start receiving job alerts\n"
            "/stop - Unsubscribe from job alerts\n"
            "/help - Show this help message\n\n"
            "I check for new jobs regularly and will notify you "
            "when fresh opportunities matching your profile are found."
        )
        
        await update.message.reply_text(help_text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in help command: {e}")

async def error_handler(update, context):
    """Log errors caused by updates."""
    logger.error(f"Update {update} caused error: {context.error}")

def main():
    try:
        # Load existing data
        load_users()
        load_job_history()
        
        # Create the Application
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        
        # Register command handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("stop", stop))
        app.add_handler(CommandHandler("help", help_command))
        
        # Register error handler
        app.add_error_handler(error_handler)
        
        # Start the job checking loop
        asyncio.create_task(check_jobs())
        
        # Start the bot
        logger.info("Starting bot...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == "__main__":
    main()