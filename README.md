# 🌬️ WindyCheck Telegram Bot

🇬🇧 **English** | [🇷🇺 Русский](README.ru.md)

![WindyCheck Bot Cover](assets/cover_en.jpg)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![aiogram 3.x](https://img.shields.io/badge/aiogram-3.x-blueviolet.svg)](https://docs.aiogram.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**WindyCheck Bot** is a modern asynchronous Telegram bot built with Python (`aiogram 3` + `aiohttp` + `SQLite`). It tracks wind speed, gusts, weather forecasts, visualizes wind rose diagrams, and sends automated push notifications for high wind alerts.

Specifically tailored for windsurfers, kitesurfers, sailors, paragliders, and outdoor enthusiasts. Includes a pre-configured section for **Saint Petersburg and Leningrad Oblast spots** with real-time riding condition ratings!

---

## 🛠️ Features

- 🏄‍♂️ **Saint Petersburg & Leningrad Oblast Spots:** Pre-configured locations (Sestroretsk/Duny, Kronstadt, Lakhta, Zelenogorsk, Kokorevo/Ladoga, Sosnovy Bor, Komarovo) with automated riding condition quality rating.
- 🌬️ **Current Wind:** Real-time speed (m/s), gusts, direction (degrees + visual compass needle 🧭), temperature, feels-like temperature, humidity, and pressure (mmHg).
- 📅 **7-Day Forecast:** Consolidated daily forecast with automated daily verification and caching.
- ⏱️ **Hourly Forecast (24 Hours):** Detailed hourly breakdown of wind speed and gusts for the upcoming 24 hours.
- 📊 **Infographic Charts (Non-blocking Event Loop):** Generation of professional dual-panel PNG charts (`matplotlib`) displaying wind dynamics, gusts, threshold indicators, temperature, and pressure in a background thread pool (`asyncio.to_thread`).
- 🧭 **Wind Rose Diagram:** Polar diagram showing prevailing wind directions.
- 🗺️ **Interactive Maps:** Direct link generation to live weather and wind maps on [Windy.com](https://www.windy.com) for target location coordinates.
- 📍 **Favorites (My Cities):** Personal spot tracking stored per user in **SQLite** database (`aiosqlite`).
- 🔔 **Automated Wind Alerts:** Background monitoring loop every 30 minutes (`asyncio`) sending push alerts when wind speed exceeds specified user threshold, equipped with anti-spam cooldown protection.

---

## 📖 User Documentation

Full user guides are included in the repository:
* 🌐 **[User Manual (English HTML)](Wind_Tracker_Bot_Instruction.en.html)** — Interactive styled web guide in English.
* 📄 **[User Manual (Russian DOCX)](Wind_Tracker_Bot_Instruction.docx)** — Microsoft Word document format.
* 🌐 **[User Manual (Russian HTML)](Wind_Tracker_Bot_Instruction.html)** — Interactive web page guide in Russian.

---

## 🚀 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/your-username/WindyCheck_bot.git
cd WindyCheck_bot
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment variables
Copy `.env.example` to `.env` and set your API tokens:
```bash
cp .env.example .env
```

Edit `.env`:
```env
BOT_TOKEN=your_telegram_bot_token_here
OPENWEATHER_API_KEY=your_openweather_api_key_here
```

### 4. Launch the bot
```bash
python main.py
```
*(Or double-click `run.bat` on Windows)*

---

## 📋 Bot Commands

| Command | Description |
| :--- | :--- |
| `/start` | Launch bot and open interactive Main Menu |
| `/spb` | SPb & Leningrad Region spots menu with riding condition ratings |
| `/wind [city]` | Current wind speed, direction, gusts, and temperature |
| `/week [city]` | Detailed 7-day weather forecast with daily caching |
| `/forecast [city]` | Hourly 24-hour wind forecast |
| `/chart [city]` | Dual-panel infographic meteorology chart |
| `/rose [city]` | Wind Rose polar direction diagram |
| `/map [city]` | Direct link to live Windy.com map |
| `/track [city]` | Add location to Favorites |
| `/untrack [city]` | Remove location from Favorites |
| `/mywind` | Current wind summary for all saved locations |
| `/alert [speed]` | Enable push notifications for wind > X m/s |
| `/alert off` | Disable wind notifications |

---

## 🏷️ Releases & Version History

For full detailed release notes, see **[CHANGELOG.md](CHANGELOG.md)**.

### [v2.0.0] - 2026-07-29
- **SPb Wind Spots:** Pre-loaded surf/kite spots in St. Petersburg & Leningrad Oblast with automated condition ratings.
- **Weekly Weather Forecast:** 7-day forecast with daily automatic caching and verification.
- **Async Infographic Charts:** Dual-panel Matplotlib infographic generation rendered asynchronously (`asyncio.to_thread`).
- **SQLite Database Persistence:** Storage migration to `aiosqlite` with automatic JSON data importer.
- **Modular Refactoring:** Restructured codebase into clean package modules with `main.py` entrypoint.

### [v1.0.0] - 2026-07-19
- **Initial Release:** Asynchronous Telegram Bot for wind tracking, 24h forecast, wind rose charts, Windy.com map integrations, favorites, and alert notifications.

---

## 📜 License
This project is distributed under the [MIT License](LICENSE).
