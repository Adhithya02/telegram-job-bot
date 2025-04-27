import os
import logging
import json
import random
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, ContextTypes, filters

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up the bot
TOKEN = os.environ.get("TELEGRAM_TOKEN")
PORT = int(os.environ.get('PORT', 8443))

# Define conversation states
SEARCH, LOCATION, CATEGORY = range(3)

# Sample job database
JOB_DATABASE = {
    "tech": [
        {
            "title": "Senior Python Developer",
            "company": "TechCorp",
            "locations": ["New York", "Remote"],
            "salary": "$120k - $160k",
            "categories": ["Full-time", "Senior"],
            "description": "Looking for an experienced Python developer with 5+ years of experience.",
            "requirements": ["Python", "Django", "Flask", "AWS", "Docker"],
            "posted_date": "2025-04-10"
        },
        {
            "title": "Frontend React Developer",
            "company": "WebWizards",
            "locations": ["San Francisco", "Remote"],
            "salary": "$100k - $140k",
            "categories": ["Full-time", "Contract"],
            "description": "Join our team to build amazing user interfaces.",
            "requirements": ["React", "JavaScript", "TypeScript", "HTML", "CSS"],
            "posted_date": "2025-04-15"
        },
        {
            "title": "Data Scientist",
            "company": "DataDynamics",
            "locations": ["Boston", "Remote"],
            "salary": "$130k - $180k",
            "categories": ["Full-time", "Senior"],
            "description": "Apply machine learning to solve complex business problems.",
            "requirements": ["Python", "R", "SQL", "Machine Learning", "Statistics"],
            "posted_date": "2025-04-20"
        },
        {
            "title": "DevOps Engineer",
            "company": "CloudInnovate",
            "locations": ["Austin", "Remote"],
            "salary": "$115k - $150k",
            "categories": ["Full-time", "Contract"],
            "description": "Help us build and maintain our cloud infrastructure.",
            "requirements": ["AWS", "Kubernetes", "Docker", "Terraform", "CI/CD"],
            "posted_date": "2025-04-18"
        },
        {
            "title": "Junior Software Developer",
            "company": "StartupGenius",
            "locations": ["Chicago", "Remote"],
            "salary": "$70k - $90k",
            "categories": ["Full-time", "Entry Level"],
            "description": "Great opportunity for recent graduates to join a fast-growing startup.",
            "requirements": ["JavaScript", "Python", "Git", "CS Degree"],
            "posted_date": "2025-04-22"
        }
    ],
    "healthcare": [
        {
            "title": "Registered Nurse",
            "company": "City Hospital",
            "locations": ["New York", "Boston"],
            "salary": "$75k - $95k",
            "categories": ["Full-time", "Part-time"],
            "description": "Join our dedicated team of healthcare professionals.",
            "requirements": ["RN License", "2+ years experience", "BLS Certification"],
            "posted_date": "2025-04-14"
        },
        {
            "title": "Medical Technologist",
            "company": "LabCorp",
            "locations": ["Chicago", "Atlanta"],
            "salary": "$60k - $80k",
            "categories": ["Full-time"],
            "description": "Perform laboratory tests and procedures.",
            "requirements": ["MT/MLS Certification", "Laboratory experience"],
            "posted_date": "2025-04-16"
        }
    ],
    "finance": [
        {
            "title": "Financial Analyst",
            "company": "Investment Partners",
            "locations": ["New York", "Chicago"],
            "salary": "$90k - $120k",
            "categories": ["Full-time"],
            "description": "Analyze financial data and make investment recommendations.",
            "requirements": ["Finance degree", "Excel", "Financial modeling"],
            "posted_date": "2025-04-12"
        },
        {
            "title": "Accountant",
            "company": "Financial Services Inc.",
            "locations": ["Remote", "Dallas"],
            "salary": "$70k - $100k",
            "categories": ["Full-time", "Contract"],
            "description": "Manage accounting operations and financial reporting.",
            "requirements": ["CPA", "Accounting degree", "QuickBooks"],
            "posted_date": "2025-04-15"
        }
    ],
    "education": [
        {
            "title": "Mathematics Teacher",
            "company": "Lincoln High School",
            "locations": ["Seattle"],
            "salary": "$55k - $75k",
            "categories": ["Full-time"],
            "description": "Teach mathematics to high school students.",
            "requirements": ["Teaching credential", "Mathematics degree"],
            "posted_date": "2025-04-13"
        },
        {
            "title": "Online Tutor",
            "company": "LearnQuick",
            "locations": ["Remote"],
            "salary": "$25 - $40 per hour",
            "categories": ["Part-time", "Contract"],
            "description": "Provide online tutoring in various subjects.",
            "requirements": ["Bachelor's degree", "Teaching experience"],
            "posted_date": "2025-04-18"
        }
    ]
}

# Job search function
def search_jobs(query, location=None, category=None, limit=5):
    results = []
    query = query.lower()
    
    # Determine which category in our database might match the query
    target_categories = []
    
    # Simple matching logic
    if any(keyword in query for keyword in ["software", "developer", "engineer", "python", "java", 
                                         "javascript", "web", "frontend", "backend", "fullstack", 
                                         "data", "scientist", "analyst", "devops", "cloud", "ai", 
                                         "machine learning", "ml", "tech"]):
        target_categories.append("tech")
    
    if any(keyword in query for keyword in ["nurse", "doctor", "medical", "healthcare", "health", 
                                        "clinic", "hospital", "patient"]):
        target_categories.append("healthcare")
    
    if any(keyword in query for keyword in ["finance", "financial", "accountant", "accounting", 
                                        "investment", "banking", "bank", "trader"]):
        target_categories.append("finance")
    
    if any(keyword in query for keyword in ["teacher", "professor", "education", "tutor", 
                                        "school", "college", "university", "teaching"]):
        target_categories.append("education")
    
    # If no specific category matched, search all categories
    if not target_categories:
        target_categories = list(JOB_DATABASE.keys())
    
    # Search through the selected categories
    for category_key in target_categories:
        for job in JOB_DATABASE[category_key]:
            # Check if job matches query
            job_text = f"{job['title']} {job['company']} {' '.join(job['requirements'])}"
            if query in job_text.lower():
                # Check location if specified
                if location and location != "Remote":
                    if location not in job['locations'] and "Remote" not in job['locations']:
                        continue
                
                # Check category if specified and not "Any"
                if category and category != "Any":
                    if category not in job['categories']:
                        continue
                
                # Calculate days ago
                posted_date = datetime.strptime(job['posted_date'], "%Y-%m-%d")
                today = datetime.now()
                days_ago = (today - posted_date).days
                
                # Add job to results
                job_copy = job.copy()
                job_copy['posted'] = f"{days_ago} days ago"
                job_copy['url'] = f"https://example.com/jobs/{category_key}/{hash(job['title'] + job['company'])}"
                
                results.append(job_copy)
                
                if len(results) >= limit:
                    break
    
    # If still no results, return some random jobs
    if not results:
        all_jobs = []
        for category_jobs in JOB_DATABASE.values():
            all_jobs.extend(category_jobs)
        
        random_jobs = random.sample(all_jobs, min(limit, len(all_jobs)))
        
        for job in random_jobs:
            # Calculate days ago
            posted_date = datetime.strptime(job['posted_date'], "%Y-%m-%d")
            today = datetime.now()
            days_ago = (today - posted_date).days
            
            # Add job to results
            job_copy = job.copy()
            job_copy['posted'] = f"{days_ago} days ago"
            job_copy['url'] = f"https://example.com/jobs/random/{hash(job['title'] + job['company'])}"
            
            results.append(job_copy)
    
    return results

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome to JobSearchBot! I can help you find job listings from our database.\n\n"
        "Use /search to start a job search\n"
        "Use /help to see all available commands"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "JobSearchBot Commands:\n\n"
        "/start - Start the bot\n"
        "/search - Search for jobs\n"
        "/cancel - Cancel current operation\n"
        "/help - Show this help message"
    )

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("What kind of job are you looking for? (e.g., Python Developer, Nurse, Teacher)")
    return SEARCH

async def search_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.message.text
    context.user_data['query'] = query
    await update.message.reply_text(f"Looking for {query} positions. Where would you like to search? (Enter a city or 'Remote')")
    return LOCATION

async def search_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    location = update.message.text
    context.user_data['location'] = location
    
    # Categories keyboard
    categories = [["Full-time", "Part-time"], ["Contract", "Internship"], ["Entry Level", "Senior"]]
    keyboard = [[InlineKeyboardButton(cat, callback_data=cat) for cat in row] for row in categories]
    keyboard.append([InlineKeyboardButton("Any", callback_data="Any")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select job type:", reply_markup=reply_markup)
    
    return CATEGORY

async def search_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    category = query.data
    context.user_data['category'] = category
    
    job_query = context.user_data.get('query', '')
    location = context.user_data.get('location', '')
    
    await query.edit_message_text(text=f"Selected: {category}")
    await query.message.reply_text(f"Searching for {category} {job_query} jobs in {location}...")
    
    # Get jobs
    jobs = search_jobs(job_query, location, category)
    
    if jobs:
        for job in jobs:
            # Format locations
            location_str = ', '.join(job['locations'])
            
            # Format requirements
            req_str = ', '.join(job['requirements'][:3])
            if len(job['requirements']) > 3:
                req_str += '...'
            
            job_text = (
                f"🔹 *{job['title']}*\n"
                f"🏢 {job['company']}\n"
                f"📍 {location_str}\n"
                f"💰 {job['salary']}\n"
                f"🔧 Skills: {req_str}\n"
                f"⏰ Posted: {job['posted']}\n"
                f"🔗 [Apply Here]({job['url']})"
            )
            await query.message.reply_text(job_text, parse_mode="Markdown", disable_web_page_preview=True)
        
        # Add more results button
        keyboard = [[InlineKeyboardButton("More Results", callback_data="more_results")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Would you like to see more results?", reply_markup=reply_markup)
    else:
        await query.message.reply_text("Sorry, no jobs found matching your criteria. Try a different search.")
    
    return ConversationHandler.END

async def more_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    user_data = context.user_data
    job_query = user_data.get('query', '')
    location = user_data.get('location', '')
    category = user_data.get('category', 'Any')
    
    # Get more jobs
    jobs = search_jobs(job_query, location, category, limit=3)
    
    if jobs:
        for job in jobs:
            # Format locations
            location_str = ', '.join(job['locations'])
            
            # Format requirements
            req_str = ', '.join(job['requirements'][:3])
            if len(job['requirements']) > 3:
                req_str += '...'
            
            job_text = (
                f"🔹 *{job['title']}*\n"
                f"🏢 {job['company']}\n"
                f"📍 {location_str}\n"
                f"💰 {job['salary']}\n"
                f"🔧 Skills: {req_str}\n"
                f"⏰ Posted: {job['posted']}\n"
                f"🔗 [Apply Here]({job['url']})"
            )
            await query.message.reply_text(job_text, parse_mode="Markdown", disable_web_page_preview=True)
    else:
        await query.message.reply_text("No more results available. Try a new search with /search")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text('Operation cancelled. Use /search to start again.')
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.warning(f'Update "{update}" caused error "{context.error}"')
    if update and update.message:
        await update.message.reply_text("Sorry, something went wrong. Please try again later.")

def main() -> None:
    # Create application
    application = Application.builder().token(TOKEN).build()

    # Add conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('search', search_command)],
        states={
            SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_query)],
            LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_location)],
            CATEGORY: [CallbackQueryHandler(search_category)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(more_results, pattern='^more_results$'))
    application.add_error_handler(error_handler)

    # Start the Bot
    if os.environ.get('RAILWAY_STATIC_URL'):
        # Railway deployment - use webhook
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=os.environ.get('RAILWAY_STATIC_URL') + TOKEN
        )
    else:
        # Local development - use polling
        application.run_polling()

if __name__ == '__main__':
    main()