from telegram.ext import Updater, CommandHandler
import requests
import os

# Set your bot token and SerpApi key
TOKEN = '7788581404:AAF2a7p7m8ZGd6tc5DNIj9VJ9saXmTZMJdc'  # Replace with your Telegram bot token
CHAT_ID = '1806702526'  # Replace with your Telegram chat ID
SERP_API_KEY = 'b5f24ef0644d851c0ee7ce633cebceb464fee210eb80b347b7d39daf107fdbc1'  # Replace with your SerpApi key

def start(update, context):
    # Send welcome message to user
    context.bot.send_message(chat_id=update.effective_chat.id, text="Hello! I will track job updates for you.")
    # Immediately send job updates when the bot is started
    jobs = fetch_jobs("fresher developer OR data analyst OR IT jobs")
    for job in jobs:
        context.bot.send_message(chat_id=update.effective_chat.id, text=job)

def fetch_jobs(query):
    # SerpApi endpoint to search for jobs on Google
    SERP_API_URL = "https://serpapi.com/search"
    
    params = {
        'q': query,  # Query for job search (e.g., 'fresher developer OR IT')
        'location': 'remote',  # Search for remote jobs
        'engine': 'google_jobs',  # Use Google Jobs engine
        'api_key': SERP_API_KEY,  # SerpApi API Key
    }
    
    response = requests.get(SERP_API_URL, params=params)
    
    if response.status_code == 200:
        results = response.json().get("jobs_results", [])
        
        # Prepare the job listings
        job_listings = []
        for job in results:
            job_listings.append(f"{job['title']} at {job['company_name']} - {job['link']}")
        
        if not job_listings:
            return ["No jobs found."]
        return job_listings
    else:
        return ["Failed to retrieve job listings."]

def job_alert(context):
    # Search for "fresher developer OR IT jobs"
    jobs = fetch_jobs("fresher developer OR IT")
    for job in jobs:
        context.bot.send_message(chat_id=CHAT_ID, text=job)

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    
    # Schedule job every hour after the bot starts
    jq = updater.job_queue
    jq.run_repeating(job_alert, interval=3600, first=10)  # Start the periodic job updates
    
    updater.start_polling()  # Start polling for updates from Telegram
    updater.idle()  # Keep the bot running

if __name__ == "__main__":
    main()
