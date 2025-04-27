import os
import logging
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up the bot
TOKEN = os.getenv('TELEGRAM_TOKEN')

# Scraping IT Jobs from Indeed
def scrape_jobs(query="IT", location="remote", num_results=5):
    try:
        # Define the URL with the search query and location (remote or city)
        url = f"https://www.indeed.com/jobs?q={query}&l={location}"
        
        # Get the page content
        response = requests.get(url)
        
        if response.status_code != 200:
            return []

        # Parse the page content using BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all job cards on the page
        job_cards = soup.find_all('a', class_='result')
        
        jobs = []
        
        for job_card in job_cards[:num_results]:  # Limit the number of results
            title = job_card.find('h2', class_='jobTitle').get_text(strip=True)
            company = job_card.find('span', class_='companyName').get_text(strip=True)
            location = job_card.find('div', class_='companyLocation').get_text(strip=True)
            job_url = "https://www.indeed.com" + job_card['href']  # Apply link

            jobs.append({
                'title': title,
                'company': company,
                'location': location,
                'url': job_url
            })
        
        return jobs
    except Exception as e:
        logger.error(f"Error scraping jobs: {e}")
        return []

# Command to start the bot
def start(update: Update, context: CallbackContext):
    # Send a welcome message and start fetching IT jobs
    update.message.reply_text("Welcome! I can help you find IT jobs globally.")
    update.message.reply_text("Fetching the latest IT job listings...")

    # Get IT jobs using the scrape_jobs function
    jobs = scrape_jobs(query="IT", location="remote", num_results=5)

    if jobs:
        for job in jobs:
            job_text = (
                f"🔹 *{job['title']}*\n"
                f"🏢 {job['company']}\n"
                f"📍 {job['location']}\n"
                f"🔗 [Apply Here]({job['url']})"
            )
            update.message.reply_text(job_text, parse_mode='Markdown', disable_web_page_preview=True)
    else:
        update.message.reply_text("Sorry, no jobs found. Please try again later.")

# Help command handler
def help_command(update: Update, context: CallbackContext):
    update.message.reply_text(
        "JobSearchBot Commands:\n\n"
        "/start - Start the bot and see IT job listings globally\n"
        "/help - Show this help message"
    )

# Error handler
def error(update: Update, context: CallbackContext):
    logger.warning(f'Update "{update}" caused error "{context.error}"')

# Main function to set up the bot
def main():
    # Set up the Updater and Dispatcher
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    # Add command handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))

    # Add error handler
    dispatcher.add_error_handler(error)

    # Start the bot
    updater.start_polling()

    # Run the bot until you press Ctrl+C
    updater.idle()

if __name__ == '__main__':
    main()
