import logging
import time
from typing import Dict, List, Optional, Tuple
import aiohttp
import config
from models import CareerSnapshot, HeroCounters

logger = logging.getLogger(__name__)

# Русские имена героев для красивого отображения поверх ключей API
HERO_RU_MAP = {
    "ana": "Ана", "ashe": "Эш", "baptiste": "Батист", "bastion": "Бастион",
    "brigitte": "Бригитта", "cassidy": "Кэссиди", "doomfist": "Кулак Смерти",
    "dva": "D.Va", "echo": "Эхо", "freja": "Фрейя", "genji": "Гэндзи",
    "hanzo": "Хандзо", "hazard": "Хазард", "illari": "Иллари",
    "jetpack-cat": "Реактивная Киса", "junker-queen": "Королева Стервятников",
    "junkrat": "Крысавчик", "juno": "Юнона", "kiriko": "Кирико",
    "lifeweaver": "Ткач Жизни", "lucio": "Лусио", "mauga": "Мауга",
    "mei": "Мэй", "mercy": "Ангел", "moira": "Мойра", "orisa": "Ориса",
    "pharah": "Фарра", "ramattra": "Раматтра", "reaper": "Жнец",
    "reinhardt": "Райнхардт", "roadhog": "Турбосвин", "sigma": "Сигма",
    "sierra": "Сьерра", "sojourn": "Соджорн", "soldier-76": "Солдат-76",
    "sombra": "Сомбра", "symmetra": "Симметра", "torbjorn": "Торбьорн",
    "tracer": "Трейсер", "venture": "Авантюра", "widowmaker": "Роковая Вдова",
    "winston": "Уинстон", "wrecking-ball": "Таран", "zarya": "Заря",
    "zenyatta": "Дзенъятта",
    "anran": "Анран",
}

NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}


class OverFastProvider:
    def __init__(self, base_url: str = config.OVERFAST_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.global_backoff_until: float = 0.0
        self.invalid_ids: Dict[str, float] = {}  # player_id -> backoff_until

    @staticmethod
    def normalize_battletag(battletag: str) -> str:
        return battletag.strip().replace("#", "-")

    def _is_blocked(self, player_id: Optional[str] = None) -> bool:
        now = time.time()
        if now < self.global_backoff_until:
            return True
        if player_id and now < self.invalid_ids.get(player_id, 0.0):
            return True
        return False

    async def _get_json(
        self, session: aiohttp.ClientSession, path: str, params: Optional[dict] = None, player_id: Optional[str] = None
    ) -> Tuple[Optional[ object ], int, Dict[str, str]]:
        if self._is_blocked(player_id):
            return None, 429, {}

        url = f"{self.base_url}{path}"
        try:
            async with session.get(url, params=params, headers=NO_CACHE_HEADERS, timeout=20) as resp:
                headers = {k.lower(): v for k, v in resp.headers.items()}
                data = await resp.json(content_type=None)

                if isinstance(data, dict) and "retry_after" in data:
                    retry_sec = float(data.get("retry_after") or 60)
                    self.global_backoff_until = time.time() + retry_sec
                    logger.warning(f"API_BACKOFF: retry_after={retry_sec}s on {path}")
                    return None, resp.status, headers

                if resp.status == 429:
                    retry_hdr = float(headers.get("retry-after", "60"))
                    self.global_backoff_until = time.time() + retry_hdr
                    logger.warning(f"API_429: retry_after={retry_hdr}s on {path}")
                    return None, 429, headers

                if resp.status == 404 and player_id:
                    # Не долбим API одним неверным ID в течение часа
                    self.invalid_ids[player_id] = time.time() + 3600

                return data, resp.status, headers
        except Exception as e:
            logger.error(f"HTTP_ERROR on {url}: {e}")
            return None, 0, {}

    async def fetch_heroes(self, session: aiohttp.ClientSession) -> List[Tuple[str, str, str]]:
        """Возвращает список (hero_key, name_ru, role) из GET /heroes."""
        data, status, _ = await self._get_json(session, "/heroes")
        if status != 200 or not isinstance(data, list):
            return []
        result = []
        for item in data:
            if not isinstance(item, dict):
                continue
            key = item.get("key")
            role = item.get("role")
            api_name = item.get("name", key)
            if key and role:
                ru_name = HERO_RU_MAP.get(key, api_name)
                result.append((key, ru_name, role))
        return result

    async def fetch_summary(self, session: aiohttp.ClientSession, player_id: str) -> Optional[dict]:
        """GET /players/{id}/summary. При неудаче пробует поиск GET /players?name=Name."""
        pid = self.normalize_battletag(player_id)
        data, status, _ = await self._get_json(session, f"/players/{pid}/summary", player_id=pid)
        if status == 200 and isinstance(data, dict) and "error" not in data:
            return data

        # Запасной поиск по имени
        short_name = pid.split("-")[0]
        s_data, s_status, _ = await self._get_json(session, "/players", params={"name": short_name})
        if s_status == 200 and isinstance(s_data, dict):
            for candidate in s_data.get("results", []):
                if candidate.get("player_id", "").lower() == pid.lower():
                    return candidate
        return None

    async def fetch_career(
        self,
        session: aiohttp.ClientSession,
        player_id: str,
        gamemode: str,
        platform: str = config.DEFAULT_PLATFORM,
    ) -> Tuple[Optional[CareerSnapshot], int]:
        """
        Скачивает снимок карьеры и возвращает (CareerSnapshot, cache_age_sec).
        """
        pid = self.normalize_battletag(player_id)
        params = {"gamemode": gamemode, "platform": platform}
        data, status, headers = await self._get_json(
            session, f"/players/{pid}/stats/career", params=params, player_id=pid
        )
        if status != 200 or not isinstance(data, dict) or "error" in data:
            return None, 0

        cache_age = int(headers.get("age", "0") or 0)
        snapshot = parse_raw_career_json(data, taken_at=int(time.time()))
        return snapshot, cache_age


def parse_raw_career_json(raw_data: dict, taken_at: int = 0) -> CareerSnapshot:
    """
    Чистый парсер ответа /stats/career во внутренний формат CareerSnapshot.
    Все отсутствующие ключи строго заменяются на 0.
    """
    heroes: Dict[str, HeroCounters] = {}
    for hero_key, blocks in raw_data.items():
        if not isinstance(blocks, dict):
            continue
        game = blocks.get("game") or {}
        combat = blocks.get("combat") or {}
        assists = blocks.get("assists") or {}

        time_played = float(game.get("time_played", 0.0) or 0.0)
        games_played = int(game.get("games_played", 0) or 0)
        games_won = int(game.get("games_won", 0) or 0)
        games_lost = int(game.get("games_lost", 0) or 0)
        deaths = float(combat.get("deaths", 0.0) or 0.0)
        eliminations = float(combat.get("eliminations", 0.0) or 0.0)
        damage = float(combat.get("hero_damage_done", 0.0) or 0.0)
        healing = float(assists.get("healing_done", 0.0) or 0.0)

        if time_played > 0 or games_played > 0 or damage > 0 or healing > 0 or eliminations > 0:
            heroes[hero_key] = HeroCounters(
                time_played=time_played,
                deaths=deaths,
                eliminations=eliminations,
                hero_damage_done=damage,
                healing_done=healing,
                games_played=games_played,
                games_won=games_won,
                games_lost=games_lost,
            )

    return CareerSnapshot(taken_at=taken_at, heroes=heroes)
