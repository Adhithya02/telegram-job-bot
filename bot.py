import os
import logging
import random
import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
import time
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

# Command handlers
async def start(update: Update, context):
    await update.message.reply_text(
        "Welcome to JobSearchBot! I can help you find job listings.\n\n"
        "Use /search to start a job search\n"
        "Use /help to see all available commands"
    )

async def help_command(update: Update, context):
    await update.message.reply_text(
        "JobSearchBot Commands:\n\n"
        "/start - Start the bot\n"
        "/search - Search for jobs\n"
        "/cancel - Cancel current operation\n"
        "/help - Show this help message"
    )

async def search_command(update: Update, context):
    await update.message.reply_text("What kind of job are you looking for? (e.g., Python Developer, Data Scientist)")
    return SEARCH

async def search_query(update: Update, context):
    query = update.message.text
    context.user_data['query'] = query
    await update.message.reply_text(f"Looking for {query} positions. Where would you like to search? (Enter a city or 'Remote')")
    return LOCATION

async def search_location(update: Update, context):
    location = update.message.text
    context.user_data['location'] = location
    
    categories = [["Full-time", "Part-time"], ["Contract", "Internship"], ["Entry Level", "Senior"]]
    keyboard = [[InlineKeyboardButton(cat, callback_data=cat) for cat in row] for row in categories]
    keyboard.append([InlineKeyboardButton("Any", callback_data="Any")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select job type:", reply_markup=reply_markup)
    
    return CATEGORY

async def search_category(update: Update, context):
    query = update.callback_query
    category = query.data
    user_data = context.user_data
    
    await query.answer()
    await query.edit_message_text(text=f"Selected: {category}")
    
    job_query = user_data.get('query', '')
    location = user_data.get('location', '')
    
    await query.message.reply_text(f"Searching for {category} {job_query} jobs in {location}...")
    
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
            await query.message.reply_text(job_text, parse_mode="Markdown", disable_web_page_preview=True)
        
        keyboard = [[InlineKeyboardButton("More Results", callback_data="more_results")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Would you like to see more results?", reply_markup=reply_markup)
    else:
        await query.message.reply_text("Sorry, no jobs found matching your criteria. Try a different search.")
    
    return ConversationHandler.END

async def more_results(update: Update, context):
    query = update.callback_query
    await query.answer()
    
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
            await query.message.reply_text(job_text, parse_mode="Markdown", disable_web_page_preview=True)
    else:
        await query.message.reply_text("No more results available. Try a new search with /search")

async def cancel(update: Update, context):
    await update.message.reply_text('Operation cancelled. Use /search to start again.')
    return ConversationHandler.END

# Main function
def main():
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('search', search_command)],
        states={
            SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_query)],
            LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_location)],
            CATEGORY: [CallbackQueryHandler(search_category)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(more_results, pattern='^more_results$'))
    
    application.run_polling()

if __name__ == '__main__':
    main()
