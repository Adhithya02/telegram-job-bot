import requests
from telegram import Bot
from telegram.ext import Updater, CommandHandler, CallbackContext

TOKEN = '7788581404:AAF2a7p7m8ZGd6tc5DNIj9VJ9saXmTZMJdc'  # Replace with your bot token
CHAT_ID = 'https://t.me/Adhithya_02'  # Replace with your Telegram user ID

# GitHub Jobs API endpoint
GITHUB_JOBS_API_URL = "https://jobs.github.com/positions.json"

def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Hello! I will track job updates for you.")

def fetch_jobs():
    # Search for fresher jobs in the developer or IT role
    params = {
        'description': 'fresher developer OR IT',  # Keywords for fresher developer or IT roles
        'location': 'remote',  # Optional: You can change location if you want specific cities/countries
        'full_time': 'true',  # Filter for full-time jobs (optional)
    }

    response = requests.get(GITHUB_JOBS_API_URL, params=params)

    if response.status_code == 200:
        jobs = response.json()  # Parse the response as JSON

        if jobs:
            job_list = []
            for job in jobs:
                # Collecting relevant information from each job
                title = job.get('title')
                company = job.get('company')
                location = job.get('location', 'Not provided')
                job_url = job.get('url')

                # Add job details to the list
                job_list.append(f"Job: {title} at {company}\nLocation: {location}\nLink: {job_url}\n")
            return job_list
        else:
            return ["No fresher jobs found."]
    else:
        return ["Failed to fetch jobs from GitHub."]

def job_alert(context: CallbackContext):
    jobs = fetch_jobs()
    for job in jobs:
        context.bot.send_message(chat_id=CHAT_ID, text=job)

def main():
    # Set up the Updater and dispatcher
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    # Start command handler
    dp.add_handler(CommandHandler("start", start))
    
    # Schedule the job_alert function to run every hour
    jq = updater.job_queue
    jq.run_repeating(job_alert, interval=3600, first=10)
    
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
