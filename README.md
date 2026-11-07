# 🎮 Overwatch 2 Tracker Bot

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Aiogram 3](https://img.shields.io/badge/aiogram-3.x-2ba1e3.svg)](https://github.com/aiogram/aiogram)
[![Docker](https://img.shields.io/badge/docker-ready-2496ed.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Languages](https://img.shields.io/badge/languages-EN%20%7C%20RU-brightgreen.svg)](#internationalization--languages)

A modern, asynchronous Telegram bot that automatically tracks Overwatch 2 player career statistics, generates high-resolution infographic session cards, competitive rank progression graphs, and weekly activity reports.

---

## 🌟 Key Features

- **⚡ Automatic Session Tracking**: Detects when you play Quick Play or Competitive games, calculates K/D ratios, damage, healing, and eliminations.
- **📊 Pillow-Rendered Infographic Cards**:
  - **Session Cards**: Hero performance comparison against your personal baseline (better, worse, or usual) with visual delta scales.
  - **Competitive Rank Progression**: Real-time rank changes and tier tracking across Tank, Damage, and Support roles.
  - **Weekly Reports**: Comprehensive infographics featuring daily win/loss histograms, top heroes of the week, winrates, and best match days.
- **🌐 Bilingual Support (English 🇬🇧 & Russian 🇷🇺)**:
  - All bot messages, interactive reply/inline keyboards, and **rendered image cards** support both English and Russian.
  - Seamless instant language switching via `/settings`.
- **🤖 Automated Notifications**: Sends completed session cards automatically after an idle timeout without needing manual intervention.
- **🐳 Turnkey Docker Deployment**: Complete `Dockerfile` and `docker-compose.yml` for 1-minute production deployments.

---

## 🚀 Quick Start with Docker

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/)
- A Telegram Bot Token from [@BotFather](https://t.me/BotFather)
- Public Overwatch 2 profile (set career profile visibility to **Public** in game settings)

### 1. Clone repository
```bash
git clone https://github.com/xDeVghost/overwatch-tracker-bot.git
cd overwatch-tracker-bot
```

### 2. Configure environment
```bash
cp .env.example .env
```
Edit `.env` and provide your bot token:
```ini
BOT_TOKEN=123456789:ABCDefGhIJKlmNoPQRsTUVwxyZ
DEFAULT_LANGUAGE=ru   # ru or en
```

### 3. Start the bot
```bash
docker compose up -d --build
```
Check the logs:
```bash
docker compose logs -f
```

---

## 🛠 Manual Installation

If you prefer running without Docker:

### 1. Clone & Set Up Virtual Environment
```bash
git clone https://github.com/xDeVghost/overwatch-tracker-bot.git
cd overwatch-tracker-bot

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure `.env`
```bash
cp .env.example .env
```
Set your `BOT_TOKEN` in `.env`.

### 4. Run the Bot
```bash
python bot.py
```

### 5. (Optional) Run as a systemd service (Linux)
Create `/etc/systemd/system/owbot.service`:
```ini
[Unit]
Description=Overwatch Tracker Telegram Bot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/opt/owbot
ExecStart=/opt/owbot/venv/bin/python /opt/owbot/bot.py
Restart=always
RestartSec=10
EnvironmentFile=/opt/owbot/.env

[Install]
WantedBy=multi-user.target
```
Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now owbot
```

---

## ⚙️ Configuration (.env)

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | *Required* | Telegram Bot token from @BotFather |
| `DB_PATH` | `ow_sessions.db` | Path to SQLite database file |
| `DEFAULT_PLATFORM` | `pc` | Player platform (`pc` or `console`) |
| `DEFAULT_LANGUAGE` | `ru` | Default language (`ru` or `en`) |
| `OVERFAST_BASE_URL` | `https://overfast-api.tekrop.fr` | OverFast API base URL |
| `POLL_INTERVAL_SEC` | `300` | Profile polling interval in seconds (5 min) |
| `SESSION_TIMEOUT_SEC` | `900` | Inactivity time to automatically close session (15 min) |
| `MIN_SESSION_SEC` | `300` | Minimum play time to trigger a session card (5 min) |
| `OBS_SEC` | `600` | 1 observation slice (10 minutes on a hero) |
| `OBS_WINDOW` | `20` | Rolling observation window for baseline calculations |
| `MIN_OBS` | `8` | Minimum observations needed for performance verdict |

---

## 📱 Bot Commands & Usage

1. **Start & Register Profile**:
   Send `/start` or directly send your BattleTag in `Name#12345` format.
2. **Control Menu**:
   - `📊 Card Now` / `📊 Карточка сейчас`: Force generate a session card for games played so far.
   - `📅 Weekly Report` / `📅 Недельный отчёт`: Generate weekly infographic with histograms and hero breakdown.
   - `⚙️ Settings` / `⚙️ Настройки`: Choose main heroes for each role and toggle language.
3. **Language Switch**:
   Open **Settings** and press the **🌐 Language** button to instantly switch between **English 🇬🇧** and **Русский 🇷🇺**.
4. **Manual Close**:
   Send `/close` to finalize current session and receive the summary immediately.

---

## 🧪 Running Tests

To run the automated test suite:
```bash
pytest tests/ -v
```

To test card rendering demo:
```bash
python preview.py
```
This will produce `preview_session.png`, `preview_competitive.png`, and `preview_weekly.png` in the project root.

---

## 📄 License & Disclaimer

This project is licensed under the MIT License.

*Overwatch is a registered trademark of Blizzard Entertainment, Inc. This project is an independent community tool and is not affiliated with, endorsed by, or sponsored by Blizzard Entertainment.*
