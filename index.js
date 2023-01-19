const { Telegraf } = require("telegraf");
const dotenv = require("dotenv");
const { Configuration, OpenAIApi } = require("openai");
const sqlite3 = require("sqlite3").verbose();
const fs = require("fs");

dotenv.config();

const LIMIT = 100;
const TIMEOUT = 5;

const MAX_TOKENS = 150;
const TEMPERATURE = 0.7;
// const MODEL = "text-davinci-003";
const MODEL = "text-curie-001";

const config = new Configuration({
    apiKey: process.env.OPENAI_KEY,
});
const openai = new OpenAIApi(config);

const bot = new Telegraf(process.env.TELEGRAM_KEY);

const db = new sqlite3.Database("./users.db");
// Insert these tables and triggers
// "CREATE TABLE IF NOT EXISTS users (user_id INTEGER, chat_messages TEXT, message_count INTEGER, date DATETIME)"
// "CREATE TABLE log (user_id INTEGER, message TEXT, date DATETIME)"
// "CREATE TRIGGER log_delete AFTER DELETE ON users BEGIN INSERT INTO log VALUES (old.user_id, old.chat_messages, datetime('now')); END;")

db.run(
    "CREATE TABLE IF NOT EXISTS users (user_id INTEGER, chat_messages TEXT, message_count INTEGER, date DATETIME)"
);
db.run(
    "CREATE TABLE IF NOT EXISTS log (user_id INTEGER, message TEXT, date DATETIME)"
);
db.run(
    "CREATE TRIGGER IF NOT EXISTS log_delete AFTER DELETE ON users BEGIN INSERT INTO log VALUES (old.user_id, old.chat_messages, datetime('now')); END;"
);

// Update the slash commands
bot.telegram.setMyCommands([
    { command: "/help", description: "Show this message" },
    { command: "/info", description: "Show info about the bot" },
    { command: "/ask", description: "Ask the bot a question" },
    { command: "/reset", description: "Reset the chatbot" },
    {
        command: "/limit",
        description:
            "Show how many messages you have left (message limit resets every midnight UTC)",
    },
    { command: "/save", description: "Save the conversation to a txt file" },
]);

// Help command
bot.command("help", (ctx) => {
    const help_text = `Hi, I'm a chatbot (\`${MODEL}\` model from OpenAI). To get started, just type something in the chat!\n*You can use the following commands:*\n/start - Start the chatbot\n/help - Show this message\n/limit - Show how many messages you have left (message limit resets every midnight UTC)\n/save - Save the conversation to a txt file\n/reset - Reset the chatbot`;
    ctx.replyWithMarkdown(help_text);
});

bot.command("info", (ctx) => {
    const info_text = `Model: \`${MODEL}\`\nMax tokens: \`${MAX_TOKENS}\`\nTemperature: \`${TEMPERATURE}\`\nMessage limit: \`${LIMIT}\`\nMessage timeout: \`${TIMEOUT}\``;
    ctx.replyWithMarkdown(info_text);
});

bot.command("reset", (ctx) => {
    // Get users ID
    const user_id = ctx.message.from.id;
    // Get current time
    const date = new Date().toISOString().slice(0, 19).replace("T", " ");
    // If the user exists in the database, fetch his message count and store it in a variable. Delete the user from the database and insert a new user with the same ID and the same message count.
    db.get(`SELECT * FROM users WHERE user_id = ${user_id}`, (err, row) => {
        if (err) {
            console.log(err);
        } else {
            if (row) {
                const message_count = row.message_count;
                db.run(`DELETE FROM users WHERE user_id = ${user_id}`);
                db.run(
                    `INSERT INTO users VALUES (${user_id}, '', ${message_count}, '${date}')`
                );
                ctx.reply(
                    "Chat history reset! Your message count has not been reset."
                );
            } else {
                ctx.reply("You have not started a conversation yet!");
            }
        }
    });
});

bot.command("limit", (ctx) => {
    // Get users ID
    const user_id = ctx.message.from.id;
    // Get the users message count from the database
    db.get(`SELECT * FROM users WHERE user_id = ${user_id}`, (err, row) => {
        if (err) {
            console.log(err);
        } else {
            if (row) {
                const message_count = row.message_count;
                if (message_count < LIMIT) {
                    ctx.replyWithMarkdown(
                        `You have \`${LIMIT - message_count}\` messages left.`
                    );
                } else {
                    ctx.replyWithMarkdown(
                        `You have reached the message limit of \`${LIMIT}\` messages. Please wait until midnight UTC to send more messages.`
                    );
                }
            } else {
                ctx.reply("You have not started a conversation yet!");
            }
        }
    });
});

bot.command("save", (ctx) => {
    // Get users ID
    const user_id = ctx.message.from.id;
    // Get the users messages from the database
    db.get(`SELECT * FROM users WHERE user_id = ${user_id}`, (err, row) => {
        if (err) {
            console.log(err);
        } else {
            if (row) {
                const chat_messages = row.chat_messages;
                // Create a file with the users messages
                fs.writeFile(
                    `./saves/${user_id}.txt`,
                    chat_messages,
                    "utf8",
                    (err) => {
                        if (err) {
                            console.log(err);
                            ctx.replyWithMarkdown(`Error: \`${err}\``);
                        } else {
                            // Send the file to the user with a message
                            ctx.replyWithDocument(
                                { source: `./saves/${user_id}.txt` },
                                { caption: "Here is our chat history so far" }
                            );
                            // Delete the file after 1 minute
                            setTimeout(() => {
                                fs.unlink(`./saves/${user_id}.txt`, (err) => {
                                    if (err) {
                                        console.log(err);
                                        ctx.replyWithMarkdown(
                                            `Error: \`${err}\``
                                        );
                                    }
                                });
                            }, 1 * 60 * 1000);
                        }
                    }
                );
            } else {
                ctx.reply("You have not started a conversation yet!");
            }
        }
    });
});

bot.command("ask", (ctx) => {
    // Get users ID
    const user_id = ctx.message.from.id;
    // Get the users message count from the database
    // Check if the user exists in the database

    db.get(`SELECT * FROM users WHERE user_id = ${user_id}`, (err, row) => {
        if (err) {
            console.log(err);
            // Return an error message if there is an error
            ctx.replyWithMarkdown(
                `An error occured. Please try again later.\nError: \`${err}\``
            );
        } else {
            let message_count = 0;
            let chat_messages = "";
            if (row) {
                message_count = row.message_count;
                chat_messages = row.chat_messages;
            } else {
                // Create a new user in the database
                const date = new Date()
                    .toISOString()
                    .slice(0, 19)
                    .replace("T", " ");
                message_count = 0;
                chat_messages = "";
                db.run(
                    `INSERT INTO users VALUES (${user_id}, "", ${message_count}, '${date}')`
                );
            }
            // If the user has not reached the message limit, send the message to OpenAI and send the response back to the user
            if (message_count < LIMIT) {
                // Get the users message
                const message = ctx.message.text.split(" ").slice(1).join(" ");
                // Format the request to OpenAI
                const request = `You are a super advanced AI. You are talking to a human through a chat interface. Try to have a conversation with the human, while pretending to be a human yourself.\nHuman: ${message}\nAI:`;
                // Send the message to OpenAI
                const response = openai.createCompletion({
                    model: MODEL,
                    prompt: request,
                    temperature: TEMPERATURE,
                    max_tokens: MAX_TOKENS,
                    stop: ["\nHuman:", "\nAI:"],
                });
                // Send the response back to the user
                response.then((data) => {
                    const reply = data.data.choices[0].text;
                    ctx.reply(reply);
                    // Update the users message count in the database
                    db.run(
                        `UPDATE users SET message_count = message_count + 1 WHERE user_id = ${user_id}`
                    );
                });
            } else {
                ctx.replyWithMarkdown(
                    `You have reached the message limit of \`${LIMIT}\` messages. Please wait until midnight UTC to send more messages.`
                );
            }
        }
    });
});

// On every message sent (except in a group chat)
bot.on("message", (ctx) => {
    // Check if the message is from a group chat
    if (ctx.message.chat.type === "group") {
        return;
    }
    // Get users ID
    const user_id = ctx.message.from.id;
    // Get the users message count from the database
    // Check if the user exists in the database
    console.log(`SELECT * FROM users WHERE user_id = ${user_id}`);
    db.get(`SELECT * FROM users WHERE user_id = ${user_id}`, (err, row) => {
        if (err) {
            console.log(err);
            // Return an error message if there is an error
            ctx.replyWithMarkdown(
                `An error occured. Please try again later.\nError: \`${err}\``
            );
        } else {
            let message_count = 0;
            let chat_messages = "";
            if (row) {
                message_count = row.message_count;
                chat_messages = row.chat_messages;
            } else {
                // Create a new user in the database
                const date = new Date()
                    .toISOString()
                    .slice(0, 19)
                    .replace("T", " ");
                message_count = 0;
                chat_messages = "";
                console.log(
                    `INSERT INTO users VALUES (${user_id}, "", ${message_count}, '${date}')`
                );
                db.run(
                    `INSERT INTO users VALUES (${user_id}, "", ${message_count}, '${date}')`
                );
            }
            // If the user has not reached the message limit, send the message to OpenAI and send the response back to the user
            if (message_count < LIMIT) {
                // Get the users message
                const message = ctx.message.text;
                // Check if the message is using ` (backtick)
                if (message.includes("`")) {
                    ctx.reply(
                        "Please do not use the ` character in your message."
                    );
                    return;
                }
                // Format the request to OpenAI (if the user is new, send a intro message too)
                let request = "";
                if (chat_messages === "") {
                    request = `You are a super advanced AI. You are talking to a human through a chat interface. Try to have a conversation with the human, while pretending to be a human yourself.\nHuman: ${message}\nAI:`;
                } else {
                    request = `${chat_messages}\nHuman: ${message}\nAI:`;
                }

                // Send the message to OpenAI
                const response = openai.createCompletion({
                    model: MODEL,
                    prompt: request,
                    temperature: TEMPERATURE,
                    max_tokens: MAX_TOKENS,
                    stop: ["\nHuman:", "\nAI:"],
                });
                // Send the response back to the user
                response.then((data) => {
                    let reply = data.data.choices[0].text;
                    // If the reply is empty, send a default message
                    if (reply === "") {
                        reply = "I don't know what to say.";
                    }
                    // Trim the whitespaces
                    reply = reply.trim();
                    // Change the " to ' to prevent errors
                    reply = reply.replace(/"/g, "'");
                    ctx.reply(reply);
                    // Update the users message count and the messages sent in the database
                    console.log(
                        `UPDATE users SET message_count = message_count + 1 WHERE user_id = ${user_id}`
                    );
                    db.run(
                        `UPDATE users SET message_count = message_count + 1 WHERE user_id = ${user_id}`
                    );
                    // Add a whitespace to the beginning of the reply to make it look better
                    reply = " " + reply;
                    const new_chat_messages = `${request}\nHuman: ${message}\nAI:${reply}`;
                    // console.log(new_chat_messages);
                    console.log(
                        `UPDATE users SET chat_messages = '${new_chat_messages}' WHERE user_id = ${user_id}`
                    );
                    db.run(
                        `UPDATE users SET chat_messages = "${new_chat_messages}" WHERE user_id = ${user_id}`
                    );
                });
            } else {
                ctx.replyWithMarkdown(
                    `You have reached the message limit of \`${LIMIT}\` messages. Please wait until midnight UTC to send more messages.`
                );
            }
        }
    });
});

// Launch the bot
bot.launch();

// Enable graceful stop
process.once("SIGINT", () => bot.stop("SIGINT"));
process.once("SIGTERM", () => bot.stop("SIGTERM"));