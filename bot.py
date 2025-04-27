from telegram import Bot
from telegram.ext import Updater, CommandHandler
import requests
import os

# Telegram Bot Token and Chat ID
TOKEN = '7788581404:AAF2a7p7m8ZGd6tc5DNIj9VJ9saXmTZMJdc'  # Replace with your bot token
CHAT_ID = 'Adhithya_02'  # Replace with your Telegram user ID

def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Hello! I will track job updates for you.")

def fetch_jobs():
    url = 'https://jobs.github.com/positions.json'
    
    # Define the query parameters: Looking for fresher developer or IT jobs
    query = {
        'description': 'fresher developer OR IT jobs',
        'location': 'India'
    }
    
    # Make the API request to GitHub Jobs API
    response = requests.get(url, params=query)
    
    # If the request is successful, parse the data
    if response.status_code == 200:
        jobs = response.json()  # Get the job listings
        
        job_list = []
        # Limit to first 5 jobs to avoid spamming
        for job in jobs[:5]:
            job_list.append(f"📌 *{job['title']}*\n🏢 {job['company']}\n📍 {job['location']}\n🔗 {job['url']}")
        return job_list
    else:
        return ["❌ Error fetching jobs."]

def job_alert(context):
    jobs = fetch_jobs()
    for job in jobs:
        context.bot.send_message(chat_id=CHAT_ID, text=job, parse_mode="Markdown")

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))

    # Schedule job every hour (3600 seconds)
    jq = updater.job_queue
    jq.run_repeating(job_alert, interval=3600, first=10)

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
