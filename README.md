# 👕 LookCast — Weather-Smart AI Personal Stylist

> **Your intelligent Telegram assistant that builds practical, weather-adapted outfits strictly from the clothes in your actual closet.**

---

## 💡 Motivation & Inspiration

Every morning, millions of people face the classic dilemma: *"What should I wear today?"* 
Existing wardrobe applications are often too slow and tedious, forcing users to manually photograph, crop, and upload every single piece of clothing. On the flip side, generic weather apps give vague suggestions like *"Wear a light jacket"* without considering what you actually own.

**LookCast** solves this with a **zero-friction approach**:
* ❌ **No photo uploads** or tedious background removal required.
* ❌ **No theoretical recommendations** of clothes you don't have.
* ✅ **Strict actual-wardrobe matching** powered by AI guardrails.
* ✅ **Real-time weather integration** for true comfort.

---

## ⚡ What It Does

LookCast guides you through a seamless, 3-step onboarding flow:
1. **City Selection:** Fetches real-time weather metrics (temperature, precipitation, wind speed) via OpenWeatherMap API.
2. **Gender & Style Context:** Personalizes styling tone (Casual, Office, Sport, Minimalist).
3. **Natural Language Closet Input:** You simply list your clothing items in plain text (e.g., *"black jeans, white hoodie, blue denim jacket, sneakers"*).

### 🎯 Key Features
* **Decision Engine Model:** Maximizes comfort index $C \in [0, 1]$ against practical weather constraints.
* **Dynamic Exclusions:** Add constraints in natural language (e.g., *"I don't have boots"* or *"Exclude heavy coats"*) to permanently adapt recommendations without hallucinations.
* **Instant Refresh:** Click *"Try another combination"* for an instant alternative look fitting the same weather conditions.

---

## 🛠️ Built With

* **Language:** Python 3.10+
* **Framework:** `python-telegram-bot` (Async pipeline)
* **AI Engine:** Google Gemini API (`gemini-2.5-flash`)
* **Weather Data:** OpenWeatherMap API
* **Database:** SQLite (Local state & wardrobe management)
* **Concurrency:** `asyncio` (Non-blocking thread execution for high-speed response)

