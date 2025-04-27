from telegram import Bot
from telegram.ext import Application, CommandHandler
import requests
import os

# Telegram Bot Token and Chat ID
TOKEN = '7788581404:AAF2a7p7m8ZGd6tc5DNIj9VJ9saXmTZMJdc'  # Replace with your bot token
CHAT_ID = 'Adhithya_02'  # Replace with your Telegram user ID

async def start(update, context):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Hello! I will track job updates for you.")

async def fetch_jobs():
    url = 'https://jobs.github.com/positions.json'
    
    # Define the query parameters
    query = {
        'description': 'fresher developer OR IT jobs',
        'location': 'India'
    }
    
    # Make the API request to GitHub Jobs API
    response = requests.get(url, params=query)
    
    # If the request is successful, parse the data
    if response.status_code == 200:
        jobs = response.json()  # Get the job listings
        print(f"Fetched Jobs: {jobs}")  # Debugging line
        job_list = []
        for job in jobs[:5]:
            job_list.append(f"📌 *{job['title']}*\n🏢 {job['company']}\n📍 {job['location']}\n🔗 {job['url']}")
        return job_list
    else:
        return ["❌ Error fetching jobs."]

async def job_alert(context):
    print("Running job alert...")  # Debugging line
    jobs = await fetch_jobs()
    for job in jobs:
        await context.bot.send_message(chat_id=CHAT_ID, text=job, parse_mode="Markdown")

def main():
    # Create an application instance using the bot token
    application = Application.builder().token(TOKEN).build()

    # Command Handler to start the bot
    application.add_handler(CommandHandler("start", start))

    # Schedule job every hour (3600 seconds)
    application.job_queue.run_repeating(job_alert, interval=3600, first=10)

    # Start polling for updates
    application.run_polling()

if __name__ == "__main__":
    main()
