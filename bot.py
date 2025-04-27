import requests
import logging
from telegram.ext import Updater, CommandHandler
from telegram import Update
from apscheduler.schedulers.background import BackgroundScheduler

# SerpAPI configuration
SERP_API_KEY = 'b5f24ef0644d851c0ee7ce633cebceb464fee210eb80b347b7d39daf107fdbc1'  # Replace with your SerpAPI key
GITHUB_JOBS_API_URL = 'https://serpapi.com/search'  # Replace with your job search API URL

# Telegram Bot configuration
TOKEN = '7788581404:AAF2a7p7m8ZGd6tc5DNIj9VJ9saXmTZMJdc'  # Replace with your Telegram bot token
CHAT_ID = '1806702526'  # Replace with your Telegram chat ID (Get this from Telegram Bot)
    
# Logging setup for debugging
logging.basicConfig(level=logging.DEBUG)

# Function to fetch jobs using SerpAPI
def fetch_jobs(query="fresher developer OR data analyst OR IT jobs"):
    try:
        params = {
            'q': query,
            'location': 'remote',  # You can change this to a specific location if needed
            'api_key': SERP_API_KEY  # Make sure the API key is correct
        }

        # Send the request to the API
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

# /start command handler
def start(update, context):
    update.message.reply_text("Hello! I will track job updates for you.")

# Function to send job alerts periodically
def job_alert(context):
    # Fetch job listings
    jobs = fetch_jobs()

    if isinstance(jobs, list) and jobs:
        # Send job listings one by one if jobs are found
        for job in jobs:
            context.bot.send_message(chat_id=CHAT_ID, text=job)
    else:
        # Handle case where no jobs are found or an error occurred
        context.bot.send_message(chat_id=CHAT_ID, text="Failed to retrieve job listings. Please try again later.")

# Main function to start the bot
def main():
    # Create the Updater and Dispatcher
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    # Handle the /start command
    dp.add_handler(CommandHandler("start", start))

    # Set up a job queue to run job_alert every hour (3600 seconds)
    jq = updater.job_queue
    jq.run_repeating(job_alert, interval=3600, first=10)  # Fetch job updates every 1 hour

    # Start the bot
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
