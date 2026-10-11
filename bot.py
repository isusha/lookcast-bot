import os
import sqlite3
import time
import asyncio
import requests
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from google import genai

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

ai_client = genai.Client(api_key=GEMINI_API_KEY)

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect("lookcast.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            city TEXT,
            gender TEXT,
            style TEXT,
            wardrobe TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_user_pref(user_id, city=None, gender=None, style=None, wardrobe=None):
    conn = sqlite3.connect("lookcast.db")
    cursor = conn.cursor()
    cursor.execute("SELECT city, gender, style, wardrobe FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if row:
        new_city = city if city is not None else row[0]
        new_gender = gender if gender is not None else row[1]
        new_style = style if style is not None else row[2]
        new_wardrobe = wardrobe if wardrobe is not None else row[3]
        cursor.execute("UPDATE users SET city = ?, gender = ?, style = ?, wardrobe = ? WHERE user_id = ?", 
                       (new_city, new_gender, new_style, new_wardrobe, user_id))
    else:
        cursor.execute("INSERT INTO users (user_id, city, gender, style, wardrobe) VALUES (?, ?, ?, ?, ?)", 
                       (user_id, city, gender, style, wardrobe))
        
    conn.commit()
    conn.close()

def get_user_pref(user_id):
    conn = sqlite3.connect("lookcast.db")
    cursor = conn.cursor()
    cursor.execute("SELECT city, gender, style, wardrobe FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {"city": row[0], "gender": row[1], "style": row[2], "wardrobe": row[3]}
    return None

# --- WEATHER API ---
def get_weather_by_city(city_name):
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city_name}&appid={WEATHER_API_KEY}&units=metric&lang=en"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        
        if data.get("cod") != 200:
            return None

        return {
            "city": data.get("name", city_name),
            "temp": round(data["main"]["temp"]),
            "feels_like": round(data["main"]["feels_like"]),
            "humidity": data["main"]["humidity"],
            "description": data["weather"][0]["description"],
            "wind": data["wind"]["speed"]
        }
    except Exception as e:
        print("Weather request error:", e)
        return None

# --- GEMINI AI GENERATOR ---
def _sync_generate_outfit(weather, gender, style, wardrobe, event, alternative=False):
    alt_instruction = ""
    if alternative:
        alt_instruction = "IMPORTANT: Propose a DIFFERENT combination of items from their wardrobe than before."

    prompt = f"""
    You are LookCast, a personal fashion assistant.
    Build a practical outfit for today strictly using items available in the user's wardrobe. Respect any exclusions/notes.

    USER PROFILE:
    - Gender: {gender}
    - Base Style: {style}
    - Occasion/Event: {event}
    - USER'S WARDROBE & NOTES: {wardrobe}

    {alt_instruction}

    WEATHER:
    - City: {weather['city']}
    - Temp: {weather['temp']}C (feels like {weather['feels_like']}C)
    - Condition: {weather['description']}
    - Wind: {weather['wind']} m/s

    CRITICAL RULES:
    1. MATCH THE EVENT: If the event is 'Sport', the outfit MUST consist of sportswear. If the user's wardrobe DOES NOT contain appropriate items for this event (e.g., they only have skirts or formal clothes), DO NOT make up an absurd look. Instead, output: "⚠️ Your current wardrobe doesn't have suitable items for {event}. Please add sportswear using /wardrobe!"
    2. Select outfit items directly from the user's wardrobe list. DO NOT suggest items they stated they do not have.
    3. Keep it concise, clean, and formatted nicely in English.
    4. Include a short, practical weather tip.

    Response format (if items are available):
    Weather in {weather['city']}: {weather['temp']}C, {weather['description']} | Event: {event}

    Outfit (from your wardrobe):
    - Top: 
    - Bottom: 
    - Outerwear / Layer: 
    - Footwear: 

    Weather tip: [Short advice]

    💡 Got new clothes? Update your closet anytime via /wardrobe.
    """

    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = ai_client.models.generate_content(
                model='gemini-3.8-flash',
                contents=prompt
            )
            return response.text
        except Exception as e:
            print(f"Gemini attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                raise e
            time.sleep(1)

async def generate_outfit(weather, gender, style, wardrobe, event, alternative=False):
    return await asyncio.to_thread(_sync_generate_outfit, weather, gender, style, wardrobe, event, alternative)

# --- COMMAND HANDLERS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    pref = get_user_pref(user_id)

    if not pref or not pref.get("city"):
        await update.message.reply_text(
            "Hello! Welcome to LookCast — your personal weather stylist.\n\n"
            "📌 *Step 1/3:* Please enter your city name in the chat to get started (e.g., London, Astana, New York).",
            parse_mode="Markdown"
        )
    elif not pref.get("gender") or not pref.get("style"):
        await update.message.reply_text(
            f"City saved: {pref['city']}!\n\n"
            "📌 *Step 2/3:* Please set up your profile using /profile (gender & style).",
            parse_mode="Markdown"
        )
    elif not pref.get("wardrobe"):
        await update.message.reply_text(
            f"City: {pref['city']} | Gender: {pref['gender']} | Style: {pref['style']}\n\n"
            "📌 *Step 3/3:* Please add items to your wardrobe using /wardrobe before generating outfits!",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"Welcome back to LookCast!\n\n"
            f"Your saved profile:\n"
            f"• City: {pref['city']}\n"
            f"• Profile: {pref['gender']}, {pref['style']} style\n"
            f"• Wardrobe: {pref['wardrobe']}\n\n"
            "You are all set! Use /outfit to generate today's look, or update settings with /profile and /wardrobe."
        )

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    pref = get_user_pref(user_id)

    if not pref or not pref.get("city"):
        await update.message.reply_text("Please type your city name in the chat first before setting up your profile!")
        return

    keyboard = [
        [
            InlineKeyboardButton("Female", callback_data="gender_Female"),
            InlineKeyboardButton("Male", callback_data="gender_Male")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select your gender:", reply_markup=reply_markup)

async def wardrobe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    pref = get_user_pref(user_id)

    if not pref or not pref.get("city"):
        await update.message.reply_text("Please type your city name first!")
        return

    if not pref.get("gender") or not pref.get("style"):
        await update.message.reply_text("Please complete your profile first using /profile!")
        return

    current = pref.get("wardrobe")
    if current:
        msg = f"Your current wardrobe:\n\n_{current}_\n\nOptions:"
        keyboard = [
            [InlineKeyboardButton("➕ Add items or note missing clothes", callback_data="wardrobe_mode_add")],
            [InlineKeyboardButton("🔄 Clear & rewrite full list", callback_data="wardrobe_mode_clear")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        context.user_data["wardrobe_mode"] = "clear"
        await update.message.reply_text(
            "📌 *Step 3/3: Add Your Wardrobe*\n\n"
            "Type your available clothing items in the chat (e.g., 'blue jeans, white t-shirt, black jacket, sneakers').",
            parse_mode="Markdown"
        )

async def outfit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    pref = get_user_pref(user_id)

    if not pref or not pref.get("city"):
        await update.message.reply_text("⚠️ City is missing! Please type your city name first.")
        return

    if not pref.get("gender") or not pref.get("style"):
        await update.message.reply_text("⚠️ Profile incomplete! Please fill out /profile (gender & style) first.")
        return

    if not pref.get("wardrobe"):
        await update.message.reply_text("⚠️ Wardrobe is empty! Please fill out /wardrobe with your clothes first.")
        return

    keyboard = [
        [
            InlineKeyboardButton("Casual Walk", callback_data="event_Casual Walk"),
            InlineKeyboardButton("Office / Work", callback_data="event_Work Office")
        ],
        [
            InlineKeyboardButton("Party / Night Out", callback_data="event_Party"),
            InlineKeyboardButton("Date", callback_data="event_Date")
        ],
        [
            InlineKeyboardButton("Sport", callback_data="event_Sport")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("What is your plan for today?", reply_markup=reply_markup)

# --- TEXT HANDLER ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_id = update.message.from_user.id
    text = update.message.text.strip()
    pref = get_user_pref(user_id)

    mode = context.user_data.get("wardrobe_mode")
    if mode == "add":
        current = pref.get("wardrobe") if pref else ""
        updated = f"{current}, {text}" if current else text
        save_user_pref(user_id, wardrobe=updated)
        context.user_data["wardrobe_mode"] = None
        await update.message.reply_text(f"Updated wardrobe:\n_{updated}_\n\nAll set! You can now use /outfit.", parse_mode="Markdown")
        return
    elif mode == "clear":
        save_user_pref(user_id, wardrobe=text)
        context.user_data["wardrobe_mode"] = None
        await update.message.reply_text(f"Wardrobe saved:\n_{text}_\n\nAll set! You can now use /outfit.", parse_mode="Markdown")
        return

    text_lower = text.lower()
    if any(phrase in text_lower for phrase in ["no ", "don't have", "do not have", "haven't", "no have"]):
        current = pref.get("wardrobe") if pref else ""
        exclusion_note = f"EXCLUSION (User doesn't have: {text})"
        updated = f"{current}, {exclusion_note}" if current else exclusion_note
        save_user_pref(user_id, wardrobe=updated)
        await update.message.reply_text(f"Got it! Noted in your profile:\n_{updated}_", parse_mode="Markdown")
        return

    status_msg = await update.message.reply_text("Checking city...")

    weather = await asyncio.to_thread(get_weather_by_city, text)
    if weather:
        save_user_pref(user_id, city=weather['city'])
        await status_msg.edit_text(
            f"City saved: {weather['city']}!\n\n"
            "📌 Next step: Please use /profile to set your gender & style."
        )
        return

    await status_msg.edit_text("To proceed, please set up your city, /profile, or /wardrobe first.")

# --- CALLBACK HANDLER ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    if data == "wardrobe_mode_add":
        context.user_data["wardrobe_mode"] = "add"
        await query.edit_message_text("Type items to add or note missing ones (e.g. 'grey hoodie, NO boots'):")

    elif data == "wardrobe_mode_clear":
        context.user_data["wardrobe_mode"] = "clear"
        await query.edit_message_text("Type your full new wardrobe list:")

    elif data.startswith("gender_"):
        gender = data.replace("gender_", "")
        save_user_pref(user_id, gender=gender)

        keyboard = [
            [
                InlineKeyboardButton("Casual", callback_data="style_Casual"),
                InlineKeyboardButton("Smart Casual", callback_data="style_Smart Casual")
            ],
            [
                InlineKeyboardButton("Minimalist", callback_data="style_Minimalist"),
                InlineKeyboardButton("Streetwear", callback_data="style_Streetwear")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"Gender saved: {gender}.\nNext, choose your favorite base style:", reply_markup=reply_markup)

    elif data.startswith("style_"):
        style = data.replace("style_", "")
        save_user_pref(user_id, style=style)
        await query.edit_message_text(
            f"Style saved: {style}!\n\n"
            "📌 Final step: Please use /wardrobe to add your clothes before picking an outfit."
        )

    elif data.startswith("event_"):
        event = data.replace("event_", "")
        context.user_data["last_event"] = event
        pref = get_user_pref(user_id)

        await query.edit_message_text(f"Styling your look for {event}... ⏳")

        weather = await asyncio.to_thread(get_weather_by_city, pref['city'])
        if not weather:
            await query.message.reply_text("Could not retrieve weather data.")
            return

        try:
            outfit_text = await generate_outfit(
                weather, 
                pref.get("gender"), 
                pref.get("style"), 
                pref.get("wardrobe"),
                event,
                alternative=False
            )

            keyboard = [[InlineKeyboardButton("🔄 Try another combination", callback_data="alt_outfit")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.message.reply_text(outfit_text, reply_markup=reply_markup)
        except Exception as e:
            print("Gemini generation error:", e)
            await query.message.reply_text("Server is temporarily busy. Please click the button again in a moment!")

    elif data == "alt_outfit":
        pref = get_user_pref(user_id)
        event = context.user_data.get("last_event", "Casual Walk")

        await query.edit_message_text("Generating another combination... ⏳")

        weather = await asyncio.to_thread(get_weather_by_city, pref['city'])
        if not weather:
            await query.message.reply_text("Could not retrieve weather data.")
            return

        try:
            outfit_text = await generate_outfit(
                weather, 
                pref.get("gender"), 
                pref.get("style"), 
                pref.get("wardrobe"),
                event,
                alternative=True
            )

            keyboard = [[InlineKeyboardButton("🔄 Try another combination", callback_data="alt_outfit")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.message.reply_text(outfit_text, reply_markup=reply_markup)
        except Exception as e:
            print("Gemini alt error:", e)
            await query.message.reply_text("Server busy. Please click button again!")

def main():
    init_db()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("wardrobe", wardrobe_command))
    app.add_handler(CommandHandler("outfit", outfit_command))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("LookCast bot is running!")
    app.run_polling()

if __name__ == "__main__":
    main()