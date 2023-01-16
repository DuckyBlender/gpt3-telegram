import datetime
import os
import telebot
from dotenv import load_dotenv
import requests
import openai
import sqlite3

load_dotenv()

TOKEN = os.environ.get('TELEGRAM_KEY')
openai.api_key = os.environ.get("OPENAI_KEY")
bot = telebot.TeleBot(TOKEN)

# Demo handlers


@bot.message_handler(commands=['start', 'hello'])
def send_welcome(message):
    bot.reply_to(message, "Howdy, how are you doing?")


# Echo all messages
# @bot.message_handler(func=lambda msg: True)
# def echo_all(message):
#     bot.reply_to(message, message.text)

# /chat - start chat
@bot.message_handler(commands=['chat'])
def start_chat(message):
    # Log the users chat id to the database
    user_id = message.from_user.id
    # Get the expiration date (5 minutes from now)
    expiration_date = datetime.datetime.now() + datetime.timedelta(minutes=5)
    # Round the expiration date to the nearest second
    expiration_date = expiration_date.replace(microsecond=0)
    # Create an empty string for the chat messages
    chat_messages = ''
    # Connect to the database and insert the user with the expiration date
    con = sqlite3.connect('users.db')
    cursor = con.cursor()
    cursor.execute("INSERT INTO users VALUES (?, ?, ?)", (user_id, chat_messages, expiration_date))
    con.commit()
    con.close()
    
    print(f"User {user_id} started a chat session at {datetime.datetime.now()}.")
    bot.reply_to(message, 'Hi, I am a chatbot. How can I help you?')

# Get message from user and send it to the OpenAI API to get a response back. Keep the conversation going until the user does not respond for 5 minutes.
@bot.message_handler(func=lambda msg: True)
def chat(message):
    # Get response from OpenAI API
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt="Hi, I am a chatbot. How can I help you?\n\nUser: " + message.text + "\nChatbot:",
        max_tokens=150,
        temperature=0.7
    )
    bot.reply_to(message, response['choices'][0]['text'])

# Check if the users.db file exists. If not, create it and add the users table.
if not os.path.exists('users.db'):
    con = sqlite3.connect('users.db')
    cursor = con.cursor()
    cursor.execute("CREATE TABLE users (user_id INTEGER, chat_messages TEXT, expiration_date DATETIME)")
    con.commit()
    con.close()

# Start the bot
bot.infinity_polling()