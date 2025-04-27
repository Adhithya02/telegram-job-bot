import logging
from telegram.ext import Updater, CommandHandler
from apscheduler.schedulers.background import BackgroundScheduler
import requests

# SerpAPI configuration
SERP_API_KEY = 'b5f24ef0644d851c0ee7ce633cebceb464fee210eb80b347b7d39daf107fdbc1'  # Replace with your SerpAPI key
GITHUB_JOBS_API_URL = 'https://serpapi.com/search'  # Replace with the URL for your job search API

# Telegram Bot configuration
TOKEN = '7788581404:AAF2a7p7m8ZGd6tc5DNIj9VJ9saXmTZMJdc'  # Replace with your Telegram bot token
CHAT_ID = '1806702526'  # Replace with your Telegram chat ID (Get this from Telegram Bot)

# Logging setup for debugging
logging.basicConfig(level=logging.DEBUG)

def fetch_jobs(query="Jobs"):
    """Fetch jobs from the SerpAPI."""
    try:
        params = {
            'q': query,
            'api_key': SERP_API_KEY  # Make sure the API key is correct
        }

        # Removing location parameter as it might be unsupported
        response = requests.get(GITHUB_JOBS_API_URL, params=params)
        
        # Log the API response for debugging
        logging.debug(f"API Response: {response.text}")

        if response.status_code == 200:
            data = response.json()
            job_listings = data.get('jobs', [])

            if job_listings:
                # Returning formatted job listings
                return [f"{job['title']} at {job['company']} - {job['location']}" for job in job_listings]
            else:
                return ["No jobs found matching your criteria."]
        else:
            logging.error(f"Error: Unable to fetch data from API. Status code: {response.status_code}")
            return [f"Error: Unable to fetch data from API. Status code: {response.status_code}"]

    except Exception as e:
        logging.error(f"Error: {str(e)}")
        return [f"Error: {str(e)}"]

def start(update, context):
    """Handler for /start command."""
    update.message.reply_text("Hello! I will track job updates for you.")

def job_alert(context):
    """Function to send job alerts."""
    jobs = fetch_jobs()

    if isinstance(jobs, list) and jobs:
        for job in jobs:
            context.bot.send_message(chat_id=CHAT_ID, text=job)
    else:
        context.bot.send_message(chat_id=CHAT_ID, text="Failed to retrieve job listings. Please try again later.")

def main():
    """Start the bot and schedule job alerts."""
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))

    # Ensure webhook is deleted before starting polling
    updater.bot.delete_webhook()

    jq = updater.job_queue
    jq.run_repeating(job_alert, interval=3600, first=10)  # Run job_alert every 1 hour

    # Start the bot
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
