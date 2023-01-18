import datetime
import os
import telebot
from dotenv import load_dotenv
import requests
import openai
import sqlite3
import schedule
# import the thing that makes the bot type when it's thinking
from telebot import apihelper
# import the thing that adds buttons
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
# split the text into chunks
from telebot import util

load_dotenv()

TOKEN = os.environ.get('TELEGRAM_KEY')
openai.api_key = os.environ.get("OPENAI_KEY")
bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

LIMIT = 100  # Per day per user in minutes
TIMEOUT = 5  # Minutes

MAX_TOKENS = 150
TEMPERATURE = 0.7
#MODEL = "text-davinci-003"
MODEL = "text-curie-001"


# /help - Show the help message
@bot.message_handler(commands=['help'])
def help(message):
    # Send the user a message with the help text
    help_text = f"Hi, I'm a chatbot (`{MODEL}` model from OpenAI). To get started, just type something in the chat!\n*You can use the following commands:*\n/start - Start the chatbot\n/help - Show this message\n/limit - Show how many messages you have left (message limit resets every midnight UTC)\n/save - Save the conversation to a txt file\n/reset - Reset the chatbot"
    # Get the user id
    user_id = message.from_user.id
    # Get his message limit
    con = sqlite3.connect('users.db')
    cursor = con.cursor()
    cursor.execute(
        "SELECT message_count FROM users WHERE user_id = ?", (user_id,))
    # Check if this was successful
    if cursor.fetchone() is None:
        con.close()
        bot.send_message(message.chat.id, help_text, parse_mode='Markdown')
        return
    message_count = cursor.fetchone()[0]
    con.close()
    help_text += f"\n\nYou have used `{message_count}`/`{LIMIT}` messages"
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')


# /reset - Reset the chatbot
@bot.message_handler(commands=['reset'])
def reset(message):
    # Save the message count to a variable
    # Then delete the user from the database and add him again with the message count (to log the chat messages)

    user_id = message.from_user.id
    now = datetime.datetime.now()
    con = sqlite3.connect('users.db')
    cursor = con.cursor()

    # Get the message count
    try:
        cursor.execute(
            "SELECT message_count FROM users WHERE user_id = ?", (user_id,))
        message_count = cursor.fetchone()[0]
    except:
        con.close()
        bot.send_message(message.chat.id, "You have not even started a conversation yet!")
        return
        
    # Delete the user
    cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))

    # Insert the user again with the message count
    cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?)",
                   (user_id, "", message_count, now))

    con.commit()
    con.close()

    # Send the user a message to start the chat
    bot.reply_to(message, 'Hi, I am a chatbot. How can I help you?',
                 parse_mode='Markdown')

# /limit - Show how many messages you have left (message limit resets every midnight UTC)
@bot.message_handler(commands=['limit'])
def limit(message):
    user_id = message.from_user.id
    con = sqlite3.connect('users.db')
    cursor = con.cursor()
    # Get the message count
    try:
        cursor.execute(
            "SELECT message_count FROM users WHERE user_id = ?", (user_id,))
        message_count = cursor.fetchone()[0]
    except:
        con.close()
        message_count = 0
    con.close()

    if message_count > LIMIT:
        bot.reply_to(
            message, f"You have used `{message_count}`/`{LIMIT}` messages. You have exceeded your message limit. Please wait until tomorrow for more messages.", parse_mode='Markdown')
        return
    bot.reply_to(
        message, f"You have used `{message_count}`/`{LIMIT}` messages.", parse_mode='Markdown')

# /save - Save the conversation to a txt file


@bot.message_handler(commands=['save'])
def save(message):
    # Get the user id
    user_id = message.from_user.id
    # Connect to the database and get the chat messages
    con = sqlite3.connect('users.db')
    cursor = con.cursor()
    try:
        cursor.execute(
            "SELECT chat_messages FROM users WHERE user_id = ?", (user_id,))
        chat_messages = cursor.fetchone()[0]
    except:
        con.close()
        bot.send_message(message.chat.id, "You have not even started a conversation yet!")
        return
    # Remove whitespaces from the beginning and end of the string
    chat_messages = chat_messages.strip()
    con.close()
    # Save the chat messages to a txt file
    with open(f"{user_id}.txt", "w") as f:
        f.write(chat_messages)
    # Send the txt file to the user
    bot.reply_to(message, "Here is our conversation so far. Would you like to clear the conversation and start over? If so, use the /reset command.")
    bot.send_document(message.chat.id, open(f"{user_id}.txt", 'rb'))
    # Delete the txt file
    os.remove(f"{user_id}.txt")

# Get message from user and send it to the OpenAI API to get a response back. Keep the conversation going until the user does not respond for TIMEOUT minutes.
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
            bot.reply_to(
                message, f"You have reached the message limit of {LIMIT} messages.")
            return
        # Get the chat messages
        chat_messages = user[1]
        # Append the new message
        chat_messages += f"\nUser: {message.text}"
        # Update the chat messages
        cursor.execute(
            "UPDATE users SET chat_messages = ? WHERE user_id = ?", (chat_messages, user_id))
    else:
        # Insert the user
        chat_messages = f"\nUser: {message.text}"
        # Current date and time
        now = datetime.datetime.now()
        cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?)",
                       (user_id, chat_messages, 0, now))

    con.commit()
    con.close()

    convo = chat_messages

    # Append the bot prefix to the message
    chat_messages += f"\nBot:"
    # Start "typing" to the user
    bot.send_chat_action(message.chat.id, 'typing')

    # Get response from OpenAI API
    response = openai.Completion.create(
        model=MODEL,
        prompt=chat_messages,
        stop=["\nUser:", "\nBot:"],
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
    )

    # Append the response to the chat messages. Remove the one whitespace at the beginning of the response.
    response = response['choices'][0]['text']
    # Remvove whitespaces from the beginning and end of the response, but add one at the beginning
    response = response.strip()
    response = f" {response}"

    chat_messages += response

    # Update the chat messages in the database and the message count
    con = sqlite3.connect('users.db')
    cursor = con.cursor()
    cursor.execute(
        "UPDATE users SET chat_messages = ? WHERE user_id = ?", (chat_messages, user_id))
    cursor.execute(
        "UPDATE users SET message_count = message_count + 1 WHERE user_id = ?", (user_id,))
    con.commit()
    con.close()

    print(f"===\nUSER ID: {user_id}\n{chat_messages}\n===")
    # Format the response (for debugging purposes). Remove all whitespaces (spaces and newlines) from the beginning and end of the response.
    response = response.strip()
    # final_response = f"```{convo}```\n`Bot:` *{response}*"

    # Shorten the convo variable if it is longer then 4000 characters.
    if len(convo) > 3800:
        convo = f"(message shortened because of message length limit. to show entire conversation execute /save)\n{convo[-3800:]}"
    # Send the response to the user
    bot.send_message(
        message.chat.id, f"```{convo}```\n`Bot:` *{response}*", parse_mode='Markdown')


# Reset the message limits function
def reset_message_limits():
    print("Resetting message limits...")
    con = sqlite3.connect('users.db')
    cursor = con.cursor()
    cursor.execute("UPDATE users SET message_count = 0")
    con.commit()
    con.close()
    print("Reset message limits.")
    
# Execute it every midnight UTC (current time is UTC+1)
# Ignore that, execute every 10 seconds for debugging purposes
schedule.every(10).seconds.do(reset_message_limits)

# For debugging purpouses, remove the user.db at start
# if os.path.exists('users.db'):
#     os.remove('users.db')
# Check if the users.db file exists. If not, create it and add the users table.
if not os.path.exists('users.db'):
    print("Creating users.db file...")
    con = sqlite3.connect('users.db')
    cursor = con.cursor()
    cursor.execute(
        "CREATE TABLE users (user_id INTEGER, chat_messages TEXT, message_count INTEGER, date DATETIME)")
    # Log table
    cursor.execute(
        "CREATE TABLE log (user_id INTEGER, message TEXT, date DATETIME)")
    # Create a trigger to log the messages to the log table if a user is removed from the users table
    cursor.execute(
        "CREATE TRIGGER log_delete AFTER DELETE ON users BEGIN INSERT INTO log VALUES (old.user_id, old.chat_messages, datetime('now')); END;")
    con.commit()
    con.close()

# Update the slash commands on the server using requests
requests.post(f"https://api.telegram.org/bot{TOKEN}/setMyCommands", json={
    "commands": [
        {
            "command": "help",
            "description": "Get all commands and their description"
        },
        {
            "command": "reset",
            "description": "Reset the chatbot"
        },
        {
            "command": "limit",
            "description": "View your message limit"
        },
        {
            "command": "save",
            "description": "Save the chat to a txt file"
        }
    ]
})


# Start the bot
bot.infinity_polling()