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

# /reset - Reset the chatbot
@bot.message_handler(commands=['reset'])
def reset_chat(message):
    # Modify the user in the database, effectively resetting the chatbot
    # Connect to the database and insert the user with the expiration date
    user_id = message.from_user.id
    con = sqlite3.connect('users.db')
    cursor = con.cursor()

    # Update the chat messages
    cursor.execute("UPDATE users SET chat_messages = ? WHERE user_id = ?", ("", user_id))
    con.commit()
    con.close()
    
    # Send the user a message to start the chat
    bot.reply_to(message, 'Hi, I am a chatbot. How can I help you?')

# Get message from user and send it to the OpenAI API to get a response back. Keep the conversation going until the user does not respond for 5 minutes.
@bot.message_handler(func=lambda msg: True)
def chat(message):
    # Log the users chat id to the database
    user_id = message.from_user.id
    # Connect to the database and insert the user with the expiration date
    con = sqlite3.connect('users.db')
    cursor = con.cursor()
    # If the user is already in the database, get his chat messages and append the new message to it. Then we can make a new request to the OpenAI API with the old chat messages and preserve context.
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if user:
        # Get the chat messages
        chat_messages = user[1]
        # Append the new message
        chat_messages += f"\nUser: {message.text}"
        # Update the chat messages
        cursor.execute("UPDATE users SET chat_messages = ? WHERE user_id = ?", (chat_messages, user_id))
    else:
        # Insert the user
        chat_messages = f"\nUser: {message.text}"
        cursor.execute("INSERT INTO users VALUES (?, ?)", (user_id, chat_messages))
    
    con.commit()
    con.close()

    # Append the bot prefix to the message
    chat_messages += f"\nBot: "

    # Get response from OpenAI API
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=chat_messages,
        stop=["\nUser:", "\nBot:"],
        max_tokens=150,
        temperature=0.7
    )

    # Append the response to the chat messages. Remoeve the one whitespace at the beginning of the response.
    response = response['choices'][0]['text'][1:]
    chat_messages += response

    # Update the chat messages in the database
    con = sqlite3.connect('users.db')
    cursor = con.cursor()
    cursor.execute("UPDATE users SET chat_messages = ? WHERE user_id = ?", (chat_messages, user_id))
    con.commit()
    con.close()

    print(f"===\nUSER: {message.text}\nPROMPT: {chat_messages}\nRESPONSE: {response}\n===")
    # Format the response (for debugging purposes)
    final_response = f"```{chat_messages}```\n\n *{response}*"
    bot.reply_to(message, final_response, parse_mode='Markdown')


# For debugging purpouses, remove the user.db at start
# if os.path.exists('users.db'):
#     os.remove('users.db')

# Check if the users.db file exists. If not, create it and add the users table.
if not os.path.exists('users.db'):
    print("Creating users.db file...")
    con = sqlite3.connect('users.db')
    cursor = con.cursor()
    cursor.execute("CREATE TABLE users (user_id INTEGER, chat_messages TEXT)")
    con.commit()
    con.close()

# Start the bot
bot.infinity_polling()