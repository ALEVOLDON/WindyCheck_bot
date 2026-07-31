# Changelog

All notable changes to the **WindyCheck Telegram Bot** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [v2.0.0] - 2026-07-29

### Added
- **St. Petersburg & Leningrad Oblast Spots:** Added pre-configured watersport spots (Sestroretsk/Duny, Kronstadt, Lakhta, Zelenogorsk, Kokorevo/Ladoga, Sosnovy Bor, Komarovo) with automated riding condition ratings for windsurfing and kitesurfing.
- **Weekly Weather Forecast (5-7 Days):** Added consolidated daily forecast support with automated once-per-day caching mechanism.
- **SQLite Database Persistence:** Integrated `aiosqlite` storage with automated JSON migration for user favorites and alert preferences.
- **Modular Package Structure:** Refactored monolithic bot script into clean modules (`bot/config`, `database`, `services`, `handlers`, `keyboards`, `utils`) with `main.py` entry point.
- **FSM Alert Thresholds:** Added Finite State Machine flow for setting alert thresholds interactively.

### Changed
- **Asynchronous Chart Rendering:** Offloaded `matplotlib` chart creation to background worker threads via `asyncio.to_thread` to prevent blocking the main asyncio event loop.
- **HTTP Client Session Management:** Optimized `aiohttp.ClientSession` reuse across weather service calls.

### Fixed
- **Spot GPS Coordinates Resolver:** Fixed auto-resolution of exact coordinates for St. Petersburg spot queries in OpenWeather requests.
- **Message Attribute Mutation Error:** Fixed `aiogram 3` / `pydantic v2` frozen `Message` instance modification error.

---

## [v1.0.0] - 2026-07-19

### Added
- **Initial Bot Release:** Core asynchronous Telegram bot built with `aiogram 3` and `aiohttp`.
- **Current Wind & Weather:** Fetching real-time wind speed, gusts, direction, temperature, feels-like temperature, humidity, and atmospheric pressure.
- **24-Hour Hourly Forecast:** Detailed breakdown of wind conditions over the next 24 hours.
- **Wind Rose Diagrams:** Polar plots for wind direction visualization using `matplotlib`.
- **Windy.com Integration:** Automatic link generation to live weather maps centered on city coordinates.
- **Favorites System:** Subscribing and tracking user favorite spots via `/track`, `/untrack`, and `/mywind`.
- **Background Alert Notifications:** Automated background worker checking weather every 30 minutes and delivering push alerts when wind speed exceeds threshold limits.
