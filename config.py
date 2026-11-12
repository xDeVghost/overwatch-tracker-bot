import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "ow_sessions.db")
OVERFAST_BASE_URL = os.getenv("OVERFAST_BASE_URL", "https://overfast-api.tekrop.fr")
DEFAULT_PLATFORM = os.getenv("DEFAULT_PLATFORM", "pc")
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "ru")

# Тайминги опроса и сессий (секунды)
POLL_INTERVAL_SEC = int(os.getenv("POLL_INTERVAL_SEC", "60"))       # 60 секунд (1 минута) опрос
SESSION_TIMEOUT_SEC = int(os.getenv("SESSION_TIMEOUT_SEC", "1200"))  # 20 минут тишины для авто-закрытия сессии
MIN_SESSION_SEC = int(os.getenv("MIN_SESSION_SEC", "300"))           # минимум 5 минут игры (или >= 1 матча)
# GAP_FACTOR — зарезервировано для будущей логики пропуска пауз (пока не используется)
# GAP_FACTOR = int(os.getenv("GAP_FACTOR", "3"))

# Параметры наблюдений и норм
OBS_SEC = int(os.getenv("OBS_SEC", "600"))           # 1 наблюдение = 10 минут на герое
OBS_WINDOW = int(os.getenv("OBS_WINDOW", "20"))      # окно последних наблюдений для расчёта нормы
MIN_OBS = int(os.getenv("MIN_OBS", "8"))             # минимум наблюдений для выдачи вердикта

# Флаг режима «ворота» по /summary
USE_SUMMARY_GATE = os.getenv("USE_SUMMARY_GATE", "false").lower() == "true"
HEROES_REFRESH_SEC = 86400  # обновление списка героев раз в сутки
