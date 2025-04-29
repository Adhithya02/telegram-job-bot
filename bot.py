import asyncio
import logging
import re
import os
import pickle
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from job_scrapers import (
    fetch_from_linkedin,
    fetch_from_remoteok,
    fetch_from_stackoverflow,
    fetch_from_internshala,
    fetch_from_freshersworld
)

# ---------------- Configuration ----------------
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # Replace with your actual token

# ---------------- Logging Setup ----------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------------- Global Data Stores ----------------
subscribed_users = set()
sent_jobs = set()
job_sources = ["linkedin", "remoteok", "stackoverflow", "internshala", "freshersworld"]
source_index = 0

# ---------------- File Paths ----------------
USERS_FILE = "users.pkl"
HISTORY_FILE = "history.pkl"

# ---------------- Utility Functions ----------------
def load_users():
    global subscribed_users
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "rb") as f:
            subscribed_users.update(pickle.load(f))

def save_users():
    with open(USERS_FILE, "wb") as f:
        pickle.dump(subscribed_users, f)

def load_job_history():
    global sent_jobs
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "rb") as f:
            sent_jobs.update(pickle.load(f))

def save_job_history():
    with open(HISTORY_FILE, "wb") as f:
        pickle.dump(sent_jobs, f)

def normalize_job_title(title):
    title = re.sub(r"[^a-zA-Z0-9 ]", "", title.lower())
    return re.sub(r"\s+", " ", title).strip()

def is_target_job(title):
    keywords = [
        "developer", "software engineer", "frontend", "backend", "fullstack",
        "data analyst", "qa", "tester", "cybersecurity", "ui", "ux", "designer"
    ]
    title_lower = title.lower()
    return any(kw in title_lower for kw in keywords)

def rotate_job_sources():
    global source_index
    def next_source():
        nonlocal source_index
        source = job_sources[source_index]
        source_index = (source_index + 1) % len(job_sources)
        return source
    return next_source

# ---------------- Scraper Dispatcher ----------------
async def check_job_source(source):
    logger.info(f"Checking {source}...")
    fetcher = {
        "linkedin": fetch_from_linkedin,
        "remoteok": fetch_from_remoteok,
        "stackoverflow": fetch_from_stackoverflow,
        "internshala": fetch_from_internshala,
        "freshersworld": fetch_from_freshersworld
    }.get(source)

    if fetcher:
        try:
            jobs = await fetcher()
            await send_jobs_to_users(jobs)
        except Exception as e:
            logger.error(f"Error fetching from {source}: {e}")
    else:
        logger.warning(f"No scraper defined for {source}")

# ---------------- Send Jobs to Users ----------------
async def send_jobs_to_users(jobs):
    try:
        if not subscribed_users or not jobs:
            return
            
        bot = Bot(BOT_TOKEN)
        
        # Filter to only include target roles and new jobs
        new_jobs = []
        for job_title, link in jobs:
            if is_target_job(job_title):
                # Normalize job title to avoid duplicates with slight differences
                normalized_title = normalize_job_title(job_title)
                unique_id = f"{normalized_title}_{link}"
                
                if unique_id not in sent_jobs:
                    sent_jobs.add(unique_id)
                    # Clean job title of any special characters that might break Markdown
                    clean_title = job_title.replace("*", "").replace("_", "").replace("`", "").replace("[", "").replace("]", "")
                    new_jobs.append((clean_title, link))
        
        if not new_jobs:
            return
            
        logger.info(f"Sending {len(new_jobs)} new jobs to {len(subscribed_users)} users")
        
        # Group jobs into batches to avoid sending too many messages at once
        # Send up to 10 jobs in one message
        grouped_jobs = []
        current_group = []
        
        for job_title, link in new_jobs:
            current_group.append((job_title, link))
            if len(current_group) >= 10:
                grouped_jobs.append(current_group)
                current_group = []
                
        if current_group:  # Add any remaining jobs
            grouped_jobs.append(current_group)
            
        # Send each group as a message to each subscribed user
        for user_id in subscribed_users:
            try:
                for job_group in grouped_jobs:
                    message = "🚨 *New Entry-Level Tech Jobs* 🚨\n\n"
                    for i, (job_title, link) in enumerate(job_group, 1):
                        message += f"{i}. [{job_title}]({link})\n\n"
                    
                    message += "\n_Use /stop to unsubscribe_"
                    
                    # Send with markdown formatting and disable web page preview
                    await bot.send_message(
                        chat_id=user_id,
                        text=message,
                        parse_mode="Markdown",
                        disable_web_page_preview=True
                    )
                    
                    # Add a small delay between messages to avoid hitting rate limits
                    await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Failed to send jobs to user {user_id}: {e}")
                
        # Save job history after successful sending
        save_job_history()
    except Exception as e:
        logger.error(f"Error sending jobs to users: {e}")

# ---------------- Periodic Job Checker ----------------
async def check_jobs():
    try:
        get_next_source = rotate_job_sources()
        
        while True:
            # Check one source at a time in rotation
            source_name = get_next_source()
            await check_job_source(source_name)
            
            # Save job history and users data periodically
            save_job_history()
            save_users()
            
            # Wait before checking the next source (1 minute rotation)
            await asyncio.sleep(60)
    except Exception as e:
        logger.error(f"Error in check_jobs loop: {e}")

# ---------------- Command Handlers ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message when the command /start is issued."""
    try:
        user_id = update.effective_user.id
        subscribed_users.add(user_id)
        save_users()
        
        welcome_message = (
            "👋 *Welcome to the Entry-Level Job Alert Bot!* 👋\n\n"
            "I'll send you freshly posted entry-level tech job opportunities including:\n"
            "- Developer positions (frontend, backend, full-stack)\n"
            "- Data Analyst roles\n"
            "- QA Testers\n"
            "- Cybersecurity positions\n"
            "- UI/UX Designer jobs\n\n"
            "You're now subscribed! You'll receive notifications when new jobs match your profile.\n\n"
            "📝 *Available Commands:*\n"
            "/start - Start receiving job alerts\n"
            "/stop - Unsubscribe from job alerts\n"
            "/help - Show available commands"
        )
        
        await update.message.reply_text(welcome_message, parse_mode="Markdown")
        logger.info(f"User {user_id} subscribed to job alerts")
    except Exception as e:
        logger.error(f"Error in start command: {e}")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unsubscribes the user when the command /stop is issued."""
    try:
        user_id = update.effective_user.id
        if user_id in subscribed_users:
            subscribed_users.remove(user_id)
            save_users()
            
        await update.message.reply_text(
            "You've been unsubscribed from job alerts. "
            "Use /start to subscribe again anytime."
        )
        logger.info(f"User {user_id} unsubscribed from job alerts")
    except Exception as e:
        logger.error(f"Error in stop command: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends help info when the command /help is issued."""
    try:
        help_text = (
            "🤖 *Entry-Level Job Alert Bot Help* 🤖\n\n"
            "I send you fresh entry-level tech job opportunities.\n\n"
            "📝 *Available Commands:*\n"
            "/start - Start receiving job alerts\n"
            "/stop - Unsubscribe from job alerts\n"
            "/help - Show this help message\n\n"
            "I check for new jobs regularly and will notify you "
            "when fresh opportunities matching your profile are found."
        )
        
        await update.message.reply_text(help_text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in help command: {e}")

async def error_handler(update, context):
    """Log errors caused by updates."""
    logger.error(f"Update {update} caused error: {context.error}")

# ---------------- Bot Startup ----------------
def main():
    try:
        # Load existing data
        load_users()
        load_job_history()
        
        # Create the Application
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        
        # Register command handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("stop", stop))
        app.add_handler(CommandHandler("help", help_command))
        
        # Register error handler
        app.add_error_handler(error_handler)
        
        # Start the job checking loop
        asyncio.create_task(check_jobs())
        
        # Start the bot
        logger.info("Starting bot...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == "__main__":
    main()
