from telegram import Bot
from telegram.ext import Updater, CommandHandler
import requests

TOKEN = '7788581404:AAF2a7p7m8ZGd6tc5DNIj9VJ9saXmTZMJdc'  # Replace with your bot token
CHAT_ID = 'Adhithya_02'  # Replace with your Telegram user ID

def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Hello! I will track job updates for you.")

def fetch_jobs():
    # Dummy job message for now
    return ["Sample Job: Fresher Software Developer at ABC Corp"]

def job_alert(context):
    jobs = fetch_jobs()
    for job in jobs:
        context.bot.send_message(chat_id=CHAT_ID, text=job)

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    
    # Schedule job every hour
    jq = updater.job_queue
    jq.run_repeating(job_alert, interval=3600, first=10)
    
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
