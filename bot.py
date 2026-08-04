import logging
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# Replace with your bot token
TOKEN = '8981863184:AAFc5_NqMUx6y04kc3niCbA5Aj1o5mi5JSU'

# Start command
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Hello! Send me your Python code, and I will run it for you.')

# Run command
def run_code(update: Update, context: CallbackContext) -> None:
    code = update.message.text
    code = code.replace('/run ', '')  # Remove the /run command

    try:
        # Execute the code
        result = eval(code)
        update.message.reply_text(f'Output: {result}')
    except Exception as e:
        update.message.reply_text(f'Error: {e}')

def main() -> None:
    updater = Updater(TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("run", run_code))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
