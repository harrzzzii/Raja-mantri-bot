import os
import random
import asyncio
import psycopg2
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = "YOUR_BOT_USERNAME"

# DB connection
conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    name TEXT,
    score INT DEFAULT 0
)
""")
conn.commit()

rooms = {}

def add_score(user_id, name, points):
    cur.execute("""
    INSERT INTO users (user_id, name, score)
    VALUES (%s, %s, %s)
    ON CONFLICT (user_id)
    DO UPDATE SET score = users.score + %s
    """, (user_id, name, points, points))
    conn.commit()

def get_leaderboard():
    cur.execute("SELECT name, score FROM users ORDER BY score DESC LIMIT 10")
    return cur.fetchall()

# START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    user = update.effective_user

    if args and args[0].startswith("join_"):
        room_id = args[0].split("_")[1]
        if room_id in rooms:
            rooms[room_id]["players"].append(user)
            await update.message.reply_text("✅ Joined via invite!")
            return

    keyboard = [
        [InlineKeyboardButton("🎮 Create Game", callback_data="create")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard")]
    ]
    await update.message.reply_text("👋 Welcome!", reply_markup=InlineKeyboardMarkup(keyboard))

# BUTTON HANDLER
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    if query.data == "create":
        room_id = str(random.randint(1000, 9999))
        rooms[room_id] = {"players": [user], "roles": {}}

        invite = f"https://t.me/{BOT_USERNAME}?start=join_{room_id}"

        keyboard = [
            [InlineKeyboardButton("▶️ Start Game", callback_data=f"start_{room_id}")]
        ]

        await query.edit_message_text(
            f"🏠 Game Created!\nInvite friends:\n{invite}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data.startswith("start_"):
        room_id = query.data.split("_")[1]
        room = rooms[room_id]

        if len(room["players"]) < 4:
            await query.answer("Need 4 players!")
            return

        roles = ["Raja 👑", "Mantri 🧠", "Chor 🕵️", "Sipahi 👮"]
        random.shuffle(roles)

        for i, player in enumerate(room["players"][:4]):
            role = roles[i]
            room["roles"][player.id] = role
            try:
                await context.bot.send_message(player.id, f"🎭 Your role: {role}")
            except:
                pass

        await context.bot.send_message(query.message.chat_id, "⏳ Starting game...")
        await asyncio.sleep(2)

        # Reveal Raja
        for pid, role in room["roles"].items():
            if "Raja" in role:
                await context.bot.send_message(query.message.chat_id, f"👑 Raja is {pid}")

        # Guess buttons
        keyboard = []
        for p in room["players"]:
            keyboard.append([InlineKeyboardButton(p.first_name, callback_data=f"guess_{room_id}_{p.id}")])

        await context.bot.send_message(
            query.message.chat_id,
            "🧠 Mantri, find the Chor:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data.startswith("guess_"):
        _, room_id, guessed = query.data.split("_")
        guessed = int(guessed)

        room = rooms[room_id]

        mantri = chor = None
        for pid, role in room["roles"].items():
            if "Mantri" in role:
                mantri = pid
            if "Chor" in role:
                chor = pid

        if user.id != mantri:
            await query.answer("Only Mantri plays!")
            return

        if guessed == chor:
            add_score(mantri, user.first_name, 100)
            result = "✅ Correct!"
        else:
            add_score(chor, "Chor", 100)
            result = "❌ Wrong!"

        data = get_leaderboard()
        text = result + "\n\n🏆 Leaderboard:\n"
        for i, (name, score) in enumerate(data, 1):
            text += f"{i}. {name} - {score}\n"

        await query.edit_message_text(text)

    elif query.data == "leaderboard":
        data = get_leaderboard()
        text = "🏆 Top Players:\n\n"
        for i, (name, score) in enumerate(data, 1):
            text += f"{i}. {name} - {score}\n"

        await query.edit_message_text(text)

# RUN
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))

app.run_polling()
