import os
import logging
import requests
from bs4 import BeautifulSoup
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackQueryHandler
)
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
        request_timestamps = [t for t in request_timestamps if current_time - t < 60]
        if len(request_timestamps) >= MAX_REQUESTS_PER_MINUTE:
            return "Too many requests. Please try again later."
        request_timestamps.append(current_time)
        return f(*args, **kwargs)
    return wrapper

# Mock job scraper
@rate_limit
def scrape_jobs(query, location=None, num_results=5):
    try:
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

        for _ in range(min(num_results, 5)):
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

def start(update, context):
    update.message.reply_text(
        "Welcome to JobSearchBot! Here are some current *IT job listings* 👇",
        parse_mode=telegram.ParseMode.MARKDOWN
    )

    # Show IT jobs automatically
    jobs = scrape_jobs("IT", location="Remote")

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
        update.message.reply_text("Sorry, couldn't find any IT jobs at the moment.")

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

    categories = [["Full-time", "Part-time"], ["Contract", "Internship"], ["Entry Level", "Senior"]]
    keyboard = [[InlineKeyboardButton(cat, callback_data=cat) for cat in row] for row in categories]
    keyboard.append([InlineKeyboardButton("Any", callback_data="Any")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Select job type:", reply_markup=reply_markup)

    return CATEGORY

def search_category(update, context):
    query = update.callback_query
    category = query.data
    user_data = context.user_data

    query.answer()
    query.edit_message_text(text=f"Selected: {category}")

    job_query = user_data.get('query', '')
    location = user_data.get('location', '')

    query.message.reply_text(f"Searching for {category} {job_query} jobs in {location}...")

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

        keyboard = [[InlineKeyboardButton("More Results", callback_data="more_results")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.message.reply_text("Would you like to see more results?", reply_markup=reply_markup)
    else:
        query.message.reply_text("Sorry, no jobs found matching your criteria. Try a different search.")

    return ConversationHandler.END

def more_results(update, context):
    query = update.callback_query
    query.answer()

    user_data = context.user_data
    job_query = user_data.get('query', '')
    location = user_data.get('location', '')

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
    if update and update.message:
        update.message.reply_text("Sorry, something went wrong. Please try again later.")

def main():
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('search', search_command)],
        states={
            SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_query)],
            LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_location)],
            CATEGORY: [CallbackQueryHandler(search_category)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(CallbackQueryHandler(more_results, pattern='^more_results$'))
    dispatcher.add_error_handler(error)

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
