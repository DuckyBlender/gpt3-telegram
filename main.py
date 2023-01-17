import datetime
import os
import telebot
from dotenv import load_dotenv
import requests
import openai
import sqlite3
# import the thing that makes the bot type when it's thinking
from telebot import apihelper
# import the thing that adds buttons
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

load_dotenv()

TOKEN = os.environ.get('TELEGRAM_KEY')
openai.api_key = os.environ.get("OPENAI_KEY")
bot = telebot.TeleBot(TOKEN)

LIMIT = 100

# Demo handlers


# @bot.message_handler(commands=['start', 'hello'])
# def send_welcome(message):
#     bot.reply_to(message, "Howdy, how are you doing?")


# Echo all messages
# @bot.message_handler(func=lambda msg: True)
# def echo_all(message):
#     bot.reply_to(message, message.text)

# /reset - Reset the chatbot
@bot.message_handler(commands=['reset'])
def reset_chat(message):
    # Save the message count to a variable
    # Then delete the user from the database and add him again with the message count (to log the chat messages)

    user_id = message.from_user.id
    now = datetime.datetime.now()
    con = sqlite3.connect('users.db')
    cursor = con.cursor()

    # Get the message count
    cursor.execute("SELECT message_count FROM users WHERE user_id = ?", (user_id,))
    message_count = cursor.fetchone()[0]

    # Delete the user
    cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))

    # Insert the user again with the message count
    cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (user_id, "", message_count, now))

    con.commit()
    con.close()
    
    # Send the user a message to start the chat
    bot.reply_to(message, 'Hi, I am a chatbot. How can I help you?')

@bot.message_handler(commands=['limit'])
def limit(message):
    user_id = message.from_user.id
    con = sqlite3.connect('users.db')
    cursor = con.cursor()
    # Get the message count
    cursor.execute("SELECT message_count FROM users WHERE user_id = ?", (user_id,))
    message_count = cursor.fetchone()[0]
    con.close()
    bot.reply_to(message, f"You have used `{message_count}`/`{LIMIT}` messages.", parse_mode='Markdown')

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
        # Get the message count
        message_count = user[2]
        # Check if the user has reached the message limit
        if message_count >= LIMIT:
            bot.reply_to(message, f"You have reached the message limit of {LIMIT} messages.")
            return
        # Get the chat messages
        chat_messages = user[1]
        # Append the new message
        chat_messages += f"\nUser: {message.text}"
        # Update the chat messages
        cursor.execute("UPDATE users SET chat_messages = ? WHERE user_id = ?", (chat_messages, user_id))
    else:
        # Insert the user
        chat_messages = f"\nUser: {message.text}"
        # Current date and time
        now = datetime.datetime.now()
        cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (user_id, chat_messages, 0, now))
    
    con.commit()
    con.close()

    convo = chat_messages

    # Append the bot prefix to the message
    chat_messages += f"\nBot:"
    # Start "typing" to the user
    bot.send_chat_action(message.chat.id, 'typing')

    # Get response from OpenAI API
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=chat_messages,
        stop=["\nUser:", "\nBot:"],
        max_tokens=150,
        temperature=0.7
    )

    # Append the response to the chat messages. Remove the one whitespace at the beginning of the response.
    response = response['choices'][0]['text']
    chat_messages += response

    # Update the chat messages in the database and the message count
    con = sqlite3.connect('users.db')
    cursor = con.cursor()
    cursor.execute("UPDATE users SET chat_messages = ? WHERE user_id = ?", (chat_messages, user_id))
    cursor.execute("UPDATE users SET message_count = message_count + 1 WHERE user_id = ?", (user_id,))
    con.commit()
    con.close()

    print(f"===\nUSER ID: {user_id}\n{chat_messages}\n===")
    # Format the response (for debugging purposes). Remove the one whitespace at the beginning of the response. 
    final_response = f"```{convo}```\n`Bot:` *{response[1:]}*"
    # what is the equivalent of this but without replying?
    bot.send_message(message.chat.id, final_response, parse_mode='Markdown')


# For debugging purpouses, remove the user.db at start
# if os.path.exists('users.db'):
#     os.remove('users.db')

# Check if the users.db file exists. If not, create it and add the users table.
if not os.path.exists('users.db'):
    print("Creating users.db file...")
    con = sqlite3.connect('users.db')
    cursor = con.cursor()
    cursor.execute("CREATE TABLE users (user_id INTEGER, chat_messages TEXT, message_count INTEGER, date DATETIME)")
    # Log table
    cursor.execute("CREATE TABLE log (user_id INTEGER, message TEXT, date DATETIME)")
    # Create a trigger to log the messages to the log table if a user is removed from the users table
    cursor.execute("CREATE TRIGGER log_delete AFTER DELETE ON users BEGIN INSERT INTO log VALUES (old.user_id, old.chat_messages, datetime('now')); END;")
    con.commit()
    con.close()

# Update the slash commands on the server using requests
requests.post("https://api.telegram.org/bot{}/setMyCommands".format(TOKEN), json={
    "commands": [
        {
            "command": "reset",
            "description": "Reset the chatbot"
        },
        {
            "command": "limit",
            "description": "View your message limit"
        }
    ]
})


# Start the bot
bot.infinity_polling()