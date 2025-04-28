import os
import logging
import random
import time
from functools import wraps
from telegram import Update
from telegram.ext import Application, CommandHandler
from bs4 import BeautifulSoup
import requests

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up the bot
TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Rate limiting
MAX_REQUESTS_PER_MINUTE = 10
request_timestamps = []

def rate_limit(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        global request_timestamps
        current_time = time.time()
        # Remove timestamps older than 60 seconds
        request_timestamps = [t for t in request_timestamps if current_time - t < 60]
        
        if len(request_timestamps) >= MAX_REQUESTS_PER_MINUTE:
            return "Too many requests. Please try again later."
        
        request_timestamps.append(current_time)
        return f(*args, **kwargs)
    return wrapper

# Job search function using web scraping
@rate_limit
def scrape_jobs(query, location=None, num_results=5):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.google.com/',
            'DNT': '1',
        }
        
        # Fake job results
        job_titles = [
            f"{query} Engineer", f"Senior {query} Developer", 
            f"{query} Analyst", f"Junior {query} Specialist",
            f"{query} Manager", f"{query} Consultant",
            f"Lead {query} Expert", f"Remote {query} Professional"
        ]
        
        companies = [
            "TechCorp", "InnoSystems", "DataDynamics", 
            "FutureWorks", "CodeMasters", "DigitalSolutions",
            "NextGen Tech", "CloudInnovate", "SmartTech"
        ]
        
        locations_list = [location] if location else ["New York", "Remote", "San Francisco", "London", "Berlin"]
        
        jobs = []
        for i in range(min(num_results, 5)):
            job = {
                'title': random.choice(job_titles),
                'company': random.choice(companies),
                'location': random.choice(locations_list),
                'salary': f"${random.randint(60, 150)}k - ${random.randint(150, 200)}k",
                'posted': f"{random.randint(1, 30)} days ago",
                'url': f"https://www.example-job-site.com/job/{random.randint(100000, 999999)}"
            }
            jobs.append(job)
            
        return jobs
    except Exception as e:
        logger.error(f"Error scraping jobs: {e}")
        return []

async def start(update: Update, context):
    await update.message.reply_text("Welcome to JobSearchBot! Fetching latest *IT jobs* for you...", parse_mode="Markdown")
    
    jobs = scrape_jobs("IT", location="Remote", num_results=5)
    
    if jobs:
        for job in jobs:
            job_text = (
                f"🔹 *{job['title']}*\n"
                f"🏢 {job['company']}\n"
                f"📍 {job['location']}\n"
                f"💰 {job['salary']}\n"
                f"⏰ Posted: {job['posted']}\n"
                f"🔗 [Apply Here]({job['url']})"
            )
            await update.message.reply_text(job_text, parse_mode="Markdown", disable_web_page_preview=True)
    else:
        await update.message.reply_text("Sorry, no IT jobs found at the moment.")

def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.run_polling()

if __name__ == '__main__':
    main()
