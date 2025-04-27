from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

# Replace 'your-telegram-bot-token' with your actual bot token
TOKEN = '7788581404:AAF2a7p7m8ZGd6tc5DNIj9VJ9saXmTZMJdc'

# Function to handle the /start command
def start(update, context):
    update.message.reply_text('Hello! I am your chatbot. How can I assist you?')

# Function to handle all text messages
def echo(update, context):
    user_message = update.message.text
    response = f'You said: {user_message}'
    update.message.reply_text(response)

# Main function to set up the bot
def main():
    updater = Updater(TOKEN, use_context=True)

    dp = updater.dispatcher

    # Handler for the /start command
    dp.add_handler(CommandHandler("start", start))

    # Handler for all text messages
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))

    # Start the bot
    updater.start_polling()

    # Run the bot until you stop it
    updater.idle()

if __name__ == '__main__':
    main()
