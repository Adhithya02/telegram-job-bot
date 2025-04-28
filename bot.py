import os
import logging
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Load bot token from environment
TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Scrape jobs from Indeed
def scrape_indeed_jobs(query="IT", location="Remote", num_results=5):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        search_query = '+'.join(query.split())
        search_location = '+'.join(location.split())
        url = f"https://www.indeed.com/jobs?q={search_query}&l={search_location}"

        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        cards = soup.find_all('a', class_='tapItem')

        jobs = []
        for card in cards[:num_results]:
            title = card.find('h2', class_='jobTitle').text.strip()
            company = card.find('span', class_='companyName').text.strip()
            location_tag = card.find('div', class_='companyLocation')
            location = location_tag.text.strip() if location_tag else "N/A"
            link = "https://www.indeed.com" + card['href']
            jobs.append({
                "title": title,
                "company": company,
                "location": location,
                "url": link
            })
        return jobs
    except Exception as e:
        logger.error(f"Scraping error: {e}")
        return []

# Handle /start command
async def start(update: Update, context):
    await update.message.reply_text("Welcome to JobSearchBot! Fetching latest *IT jobs*...", parse_mode="Markdown")

    jobs = scrape_indeed_jobs()

    if jobs:
        for job in jobs:
            text = (
                f"🔹 *{job['title']}*\n"
                f"🏢 {job['company']}\n"
                f"📍 {job['location']}\n"
                f"🔗 [Apply Here]({job['url']})"
            )
            await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)
    else:
        await update.message.reply_text("❌ No jobs found at the moment.")

# Main function to start bot
def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.run_polling()

if __name__ == "__main__":
    main()
