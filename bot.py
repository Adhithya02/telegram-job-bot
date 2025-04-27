import os
import logging
import requests
from bs4 import BeautifulSoup
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import re
import time
import random
from functools import wraps

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up the bot
TOKEN = os.environ.get("TELEGRAM_TOKEN")
PORT = int(os.environ.get('PORT', 8443))

# Define conversation states
SEARCH, LOCATION, CATEGORY = range(3)

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

        # Scrape jobs from a dummy website (substitute with a real site)
        base_url = "https://www.example-job-site.com/search"
        params = {'q': query}
        if location:
            params['l'] = location

        # Make the request to the job site
        response = requests.get(base_url, params=params, headers=headers)

        if response.status_code != 200:
            logger.error(f"Failed to retrieve data from the job site. Status code: {response.status_code}")
            return []

        # Parse the response with BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')

        # For demo, we'll simulate parsing some job listings
        jobs = []
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

# Command handlers
def start(update, context):
    update.message.reply_text(
        "Welcome to JobSearchBot! I can help you find IT job listings.\n\n"
        "Use /search to start a job search\n"
        "Use /help to see all available commands"
    )

    # Automatically trigger IT job search when /start is called
    query = 'IT'
    location = 'Remote'
    update.message.reply_text(f"Searching for IT jobs in {location}...")
    
    jobs = scrape_jobs(query, location)

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
            update.message.reply_text(job_text, parse_mode=telegram.ParseMode.MARKDOWN, disable_web_page_preview=True)
    else:
        update.message.reply_text("Sorry, no IT jobs found at the moment.")

def help_command(update, context):
    update.message.reply_text(
        "JobSearchBot Commands:\n\n"
        "/start - Start the bot\n"
        "/search - Search for jobs\n"
        "/cancel - Cancel current operation\n"
        "/help - Show this help message"
    )

def search_command(update, context):
    update.message.reply_text("What kind of job are you looking for? (e.g., Python Developer, Data Scientist)")
    return SEARCH

def search_query(update, context):
    query = update.message.text
    context.user_data['query'] = query
    update.message.reply_text(f"Looking for {query} positions. Where would you like to search? (Enter a city or 'Remote')")
    return LOCATION

def search_location(update, context):
    location = update.message.text
    context.user_data['location'] = location
    
    # Categories keyboard
    categories = [["Full-time", "Part-time"], ["Contract", "Internship"], ["Entry Level", "Senior"]]
    keyboard = [[InlineKeyboardButton(cat, callback_data=cat) for cat in row] for row in categories]
    keyboard.append([InlineKeyboardButton("Any", callback_data="Any")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Select job type:", reply_markup=reply_markup)
    
    return CATEGORY

def search_category(update, context):
    query = context.callback_query
    category = query.data
    user_data = context.user_data
    
    query.answer()
    query.edit_message_text(text=f"Selected: {category}")
    
    job_query = user_data.get('query', 'IT')
    location = user_data.get('location', 'Remote')
    
    query.message.reply_text(f"Searching for {category} {job_query} jobs in {location}...")
    
    # Get jobs
    jobs = scrape_jobs(job_query, location)
    
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
            query.message.reply_text(job_text, parse_mode=telegram.ParseMode.MARKDOWN, disable_web_page_preview=True)
        
        # Add more results button
        keyboard = [[InlineKeyboardButton("More Results", callback_data="more_results")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.message.reply_text("Would you like to see more results?", reply_markup=reply_markup)
    else:
        query.message.reply_text("Sorry, no jobs found matching your criteria. Try a different search.")
    
    return ConversationHandler.END

def more_results(update, context):
    query = context.callback_query
    query.answer()
    
    user_data = context.user_data
    job_query = user_data.get('query', 'IT')
    location = user_data.get('location', 'Remote')
    
    # Get more jobs with different random results
    jobs = scrape_jobs(job_query, location)
    
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
            query.message.reply_text(job_text, parse_mode=telegram.ParseMode.MARKDOWN, disable_web_page_preview=True)
    else:
        query.message.reply_text("No more results available. Try a new search with /search")

def cancel(update, context):
    update.message.reply_text('Operation cancelled. Use /search to start again.')
    return ConversationHandler.END

def error(update, context):
    logger.warning(f'Update "{update}" caused error "{context.error}"')
    if update.message:
        update.message.reply_text("Sorry, something went wrong. Please try again later.")

def main():
    # Create the Updater
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    # Add conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('search', search_command)],
        states={
            SEARCH: [MessageHandler(Filters.text & ~Filters.command, search_query)],
            LOCATION: [MessageHandler(Filters.text & ~Filters.command, search_location)],
            CATEGORY: [CallbackQueryHandler(search_category)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # Add handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(CallbackQueryHandler(more_results, pattern='^more_results$'))
    dispatcher.add_error_handler(error)

    # Start the Bot
    railway_url = os.environ.get('RAILWAY_STATIC_URL')
    if railway_url:
        webhook_url = railway_url.rstrip('/') + '/' + TOKEN
        print("Using webhook URL:", webhook_url)
        updater.start_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=webhook_url
        )
    else:
        print("No Railway URL found. Using polling...")
        updater.start_polling()

    updater.idle()

if __name__ == '__main__':
    main()
