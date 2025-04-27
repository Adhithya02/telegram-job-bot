import logging
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Job search function using BeautifulSoup
def get_jobs(query='IT jobs', location='remote'):
    # Construct the search URL for Indeed
    url = f'https://www.indeed.com/jobs?q={query}&l={location}'

    # Send a request to Indeed
    response = requests.get(url)
    if response.status_code != 200:
        return "Failed to retrieve data. Please try again later."

    # Parse the HTML content using BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find all job listings
    job_elements = soup.find_all('a', {'class': 'tapItem'})

    # If no jobs are found, return a message
    if not job_elements:
        return "No jobs found!"

    # Collect job titles, company names, and application links
    job_list = []
    for job in job_elements:
        job_title = job.find('span', {'class': 'jobTitle'}).text.strip()
        company_name = job.find('span', {'class': 'companyName'}).text.strip()
        job_link = 'https://www.indeed.com' + job['href']

        job_list.append(f"{job_title} at {company_name}\nApply here: {job_link}\n")

    # Return the formatted job list (limit to top 5)
    return "\n\n".join(job_list[:5])

# Command /start
def start(update: Update, context: CallbackContext):
    update.message.reply_text("Hello! I can help you search for IT jobs. Type /jobs to get started!")

# Command /jobs
def jobs(update: Update, context: CallbackContext):
    query = ' '.join(context.args) if context.args else 'IT jobs'  # Default to 'IT jobs'
    location = 'remote'  # Default location

    # Get job listings
    job_results = get_jobs(query, location)

    # Send the job results to the user
    update.message.reply_text(job_results)

# Main function to run the bot
def main():
    # Your Telegram bot token here
    token = '7788581404:AAF2a7p7m8ZGd6tc5DNIj9VJ9saXmTZMJdc'  # Replace with your bot's token

    # Create the Updater and pass it your bot's token
    updater = Updater(token, use_context=True)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # Add handlers for commands
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CommandHandler('jobs', jobs))

    # Start the bot
    updater.start_polling()

    # Run the bot until you send a signal to stop it
    updater.idle()

if __name__ == '__main__':
    main()
