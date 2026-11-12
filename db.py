import json
import sqlite3
import time
from dataclasses import asdict
from typing import Dict, List, Optional, Tuple
import config
from models import BucketState, CareerSnapshot, HeroCounters, ObservationRecord
from provider import HERO_RU_MAP

DEFAULT_HERO_ROLES = {
    # Tanks
    "dva": "tank", "doomfist": "tank", "hazard": "tank", "junker-queen": "tank",
    "mauga": "tank", "orisa": "tank", "ramattra": "tank", "reinhardt": "tank",
    "roadhog": "tank", "sigma": "tank", "winston": "tank", "wrecking-ball": "tank", "zarya": "tank",
    "domina": "tank", "doctrine": "tank", "d-mon": "tank", "d_mon": "tank",
    # Damage
    "ashe": "damage", "bastion": "damage", "cassidy": "damage", "echo": "damage",
    "genji": "damage", "hanzo": "damage", "junkrat": "damage", "mei": "damage",
    "pharah": "damage", "reaper": "damage", "sojourn": "damage", "soldier-76": "damage",
    "sombra": "damage", "symmetra": "damage", "torbjorn": "damage", "tracer": "damage",
    "venture": "damage", "widowmaker": "damage", "freja": "damage", "sierra": "damage",
    "anran": "damage", "emre": "damage",
    # Supports
    "ana": "support", "baptiste": "support", "brigitte": "support", "illari": "support",
    "jetpack-cat": "support", "juno": "support", "kiriko": "support", "lifeweaver": "support",
    "lucio": "support", "mercy": "support", "moira": "support", "zenyatta": "support",
    "mizuki": "support", "shion": "support", "wuyang": "support",
}


class Database:
    def __init__(self, db_path: str = config.DB_PATH):
        self.db_path = db_path
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_schema(self):
        with self._conn() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS heroes_catalog (
                    hero_key TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    battletag TEXT NOT NULL,
                    platform TEXT DEFAULT 'pc',
                    last_summary_updated_at INTEGER DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    avatar_url TEXT DEFAULT '',
                    ranks_json TEXT DEFAULT '',
                    language TEXT DEFAULT 'ru'
                );

                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    hero_key TEXT NOT NULL,
                    PRIMARY KEY (user_id, role)
                );

                CREATE TABLE IF NOT EXISTS career_snapshots (
                    user_id INTEGER NOT NULL,
                    gamemode TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    taken_at INTEGER NOT NULL,
                    PRIMARY KEY (user_id, gamemode)
                );

                CREATE TABLE IF NOT EXISTS observation_buckets (
                    user_id INTEGER NOT NULL,
                    gamemode TEXT NOT NULL,
                    hero_key TEXT NOT NULL,
                    time_sec REAL NOT NULL,
                    deaths REAL NOT NULL,
                    eliminations REAL NOT NULL DEFAULT 0.0,
                    damage REAL NOT NULL,
                    healing REAL NOT NULL,
                    PRIMARY KEY (user_id, gamemode, hero_key)
                );

                CREATE TABLE IF NOT EXISTS observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    gamemode TEXT NOT NULL,
                    hero_key TEXT NOT NULL,
                    output_10m REAL NOT NULL,
                    deaths_10m REAL NOT NULL,
                    eliminations_10m REAL NOT NULL DEFAULT 0.0,
                    created_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_obs_lookup
                ON observations (user_id, gamemode, hero_key, id DESC);

                CREATE TABLE IF NOT EXISTS active_sessions (
                    user_id INTEGER NOT NULL,
                    gamemode TEXT NOT NULL,
                    started_at INTEGER NOT NULL,
                    last_change_at INTEGER NOT NULL,
                    games_played INTEGER NOT NULL,
                    games_won INTEGER NOT NULL,
                    games_lost INTEGER NOT NULL,
                    last_viewed_games INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (user_id, gamemode)
                );

                CREATE TABLE IF NOT EXISTS session_heroes (
                    user_id INTEGER NOT NULL,
                    gamemode TEXT NOT NULL,
                    hero_key TEXT NOT NULL,
                    time_sec REAL NOT NULL,
                    deaths REAL NOT NULL,
                    eliminations REAL NOT NULL DEFAULT 0.0,
                    damage REAL NOT NULL,
                    healing REAL NOT NULL,
                    games_played INTEGER NOT NULL DEFAULT 0,
                    games_won INTEGER NOT NULL DEFAULT 0,
                    games_lost INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (user_id, gamemode, hero_key)
                );

                CREATE TABLE IF NOT EXISTS session_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    gamemode TEXT NOT NULL,
                    started_at INTEGER NOT NULL,
                    ended_at INTEGER NOT NULL,
                    duration_sec REAL NOT NULL,
                    games_played INTEGER NOT NULL,
                    games_won INTEGER NOT NULL,
                    games_lost INTEGER NOT NULL,
                    eliminations REAL NOT NULL DEFAULT 0.0,
                    deaths REAL NOT NULL DEFAULT 0.0,
                    damage REAL NOT NULL DEFAULT 0.0,
                    healing REAL NOT NULL DEFAULT 0.0
                );
                CREATE INDEX IF NOT EXISTS idx_hist_user_time ON session_history(user_id, ended_at DESC);

                CREATE TABLE IF NOT EXISTS session_history_heroes (
                    session_id INTEGER NOT NULL,
                    hero_key TEXT NOT NULL,
                    time_sec REAL NOT NULL,
                    eliminations REAL NOT NULL DEFAULT 0.0,
                    deaths REAL NOT NULL DEFAULT 0.0,
                    damage REAL NOT NULL DEFAULT 0.0,
                    healing REAL NOT NULL DEFAULT 0.0,
                    games_played INTEGER NOT NULL DEFAULT 0,
                    games_won INTEGER NOT NULL DEFAULT 0,
                    games_lost INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (session_id, hero_key)
                );
            """)

            # Безопасные миграции для существующих баз данных
            self._ensure_column(conn, "users", "avatar_url", "TEXT DEFAULT ''")
            self._ensure_column(conn, "users", "ranks_json", "TEXT DEFAULT ''")
            self._ensure_column(conn, "users", "language", "TEXT DEFAULT 'ru'")
            self._ensure_column(conn, "users", "last_weekly_sent_week", "TEXT DEFAULT ''")
            self._ensure_column(conn, "session_heroes", "eliminations", "REAL NOT NULL DEFAULT 0.0")
            self._ensure_column(conn, "session_heroes", "games_played", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "session_heroes", "games_won", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "session_heroes", "games_lost", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "session_history_heroes", "games_played", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "session_history_heroes", "games_won", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "session_history_heroes", "games_lost", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "observation_buckets", "eliminations", "REAL NOT NULL DEFAULT 0.0")
            self._ensure_column(conn, "active_sessions", "last_viewed_games", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "observations", "eliminations_10m", "REAL NOT NULL DEFAULT 0.0")

            # Заполняем стартовый каталог на случай, если первый старт без сети
            count = conn.execute("SELECT COUNT(*) FROM heroes_catalog").fetchone()[0]
            if count == 0:
                for k, ru_name in HERO_RU_MAP.items():
                    role = DEFAULT_HERO_ROLES.get(k, "damage")
                    conn.execute(
                        "INSERT OR IGNORE INTO heroes_catalog (hero_key, name, role, updated_at) VALUES (?, ?, ?, 0)",
                        (k, ru_name, role),
                    )

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table_name: str, col_name: str, col_type: str):
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]
        if col_name not in cols:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}")

    # --- Каталог героев ---
    def heroes_need_refresh(self, max_age_sec: int = config.HEROES_REFRESH_SEC) -> bool:
        with self._conn() as conn:
            row = conn.execute("SELECT MIN(updated_at) FROM heroes_catalog").fetchone()
            last_upd = row[0] if row and row[0] is not None else 0
            return (int(time.time()) - last_upd) >= max_age_sec

    def upsert_heroes_catalog(self, heroes: List[Tuple[str, str, str]]):
        now = int(time.time())
        with self._conn() as conn:
            for key, name, role in heroes:
                conn.execute(
                    """
                    INSERT INTO heroes_catalog (hero_key, name, role, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(hero_key) DO UPDATE SET
                        name=excluded.name, role=excluded.role, updated_at=excluded.updated_at
                    """,
                    (key, name, role, now),
                )

    def get_heroes_maps(self, lang: str = "ru") -> Tuple[Dict[str, str], Dict[str, str]]:
        """Возвращает (hero_roles, hero_names) с учетом выбранного языка."""
        with self._conn() as conn:
            rows = conn.execute("SELECT hero_key, name, role FROM heroes_catalog").fetchall()
        from i18n import get_hero_name
        roles = {r[0]: r[2] for r in rows}
        names = {r[0]: get_hero_name(r[0], lang) for r in rows}
        return roles, names

    # --- Пользователи и настройки ---
    def upsert_user(
        self,
        user_id: int,
        battletag: str,
        platform: str = config.DEFAULT_PLATFORM,
        summary_ts: int = 0,
        avatar_url: str = "",
        language: str = config.DEFAULT_LANGUAGE,
    ):
        now = int(time.time())
        with self._conn() as conn:
            # A Telegram user may re-bind the bot to another BattleTag.  All
            # snapshots, buckets and sessions belong to the old identity and
            # must be removed before the new baseline is written; otherwise
            # the next poll produces a synthetic delta between two accounts.
            old = conn.execute(
                "SELECT battletag, platform FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if old and (old[0] != battletag or old[1] != platform):
                conn.execute(
                    "DELETE FROM session_history_heroes WHERE session_id IN "
                    "(SELECT id FROM session_history WHERE user_id = ?)",
                    (user_id,),
                )
                conn.execute("DELETE FROM session_history WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM session_heroes WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM active_sessions WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM observations WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM observation_buckets WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM career_snapshots WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM user_preferences WHERE user_id = ?", (user_id,))
                conn.execute("UPDATE users SET last_weekly_sent_week = '' WHERE user_id = ?", (user_id,))

            conn.execute(
                """
                INSERT INTO users (user_id, battletag, platform, last_summary_updated_at, created_at, avatar_url, language)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    battletag=excluded.battletag,
                    platform=excluded.platform,
                    last_summary_updated_at=excluded.last_summary_updated_at,
                    avatar_url=CASE WHEN excluded.avatar_url != '' THEN excluded.avatar_url ELSE users.avatar_url END,
                    language=COALESCE(users.language, excluded.language)
                """,
                (user_id, battletag, platform, summary_ts, now, avatar_url, language),
            )

    def set_user_language(self, user_id: int, language: str):
        with self._conn() as conn:
            conn.execute("UPDATE users SET language = ? WHERE user_id = ?", (language, user_id))

    def get_user_language(self, user_id: int) -> str:
        with self._conn() as conn:
            row = conn.execute("SELECT language FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return row[0] if (row and row[0]) else config.DEFAULT_LANGUAGE

    def update_user_avatar(self, user_id: int, avatar_url: str):
        with self._conn() as conn:
            conn.execute("UPDATE users SET avatar_url = ? WHERE user_id = ?", (avatar_url, user_id))

    def update_user_summary_ts(self, user_id: int, summary_ts: int):
        with self._conn() as conn:
            conn.execute("UPDATE users SET last_summary_updated_at = ? WHERE user_id = ?", (summary_ts, user_id))

    def update_user_ranks(self, user_id: int, ranks_json: str):
        with self._conn() as conn:
            conn.execute("UPDATE users SET ranks_json = ? WHERE user_id = ?", (ranks_json, user_id))

    def get_user_ranks(self, user_id: int) -> dict:
        with self._conn() as conn:
            row = conn.execute("SELECT ranks_json FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not row or not row[0]:
            return {}
        try:
            return json.loads(row[0])
        except Exception:
            return {}

    def get_user_last_weekly(self, user_id: int) -> str:
        with self._conn() as conn:
            row = conn.execute("SELECT last_weekly_sent_week FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return row[0] if (row and row[0]) else ""

    def set_user_last_weekly(self, user_id: int, week_key: str):
        with self._conn() as conn:
            conn.execute("UPDATE users SET last_weekly_sent_week = ? WHERE user_id = ?", (week_key, user_id))

    def get_user(self, user_id: int) -> Optional[Tuple[int, str, str, int, str, str]]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT user_id, battletag, platform, last_summary_updated_at, avatar_url, COALESCE(language, 'ru') FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if not row:
            return None
        return (row[0], row[1], row[2], row[3], row[4] or "", row[5] or "ru")

    def list_users(self) -> List[Tuple[int, str, str, int, str, str]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT user_id, battletag, platform, last_summary_updated_at, COALESCE(avatar_url, ''), COALESCE(language, 'ru') FROM users"
            ).fetchall()
        return rows

    def set_preferred_hero(self, user_id: int, role: str, hero_key: str):
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO user_preferences (user_id, role, hero_key)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, role) DO UPDATE SET hero_key=excluded.hero_key
                """,
                (user_id, role, hero_key),
            )

    def get_preferences(self, user_id: int) -> Dict[str, str]:
        with self._conn() as conn:
            rows = conn.execute("SELECT role, hero_key FROM user_preferences WHERE user_id = ?", (user_id,)).fetchall()
        return {r[0]: r[1] for r in rows}

    def auto_init_preferences(self, user_id: int, qp_snap: Optional[CareerSnapshot], comp_snap: Optional[CareerSnapshot]):
        roles_map, _ = self.get_heroes_maps()
        existing = self.get_preferences(user_id)
        totals: Dict[str, float] = {}
        for snap in (qp_snap, comp_snap):
            if not snap:
                continue
            for hk, cnt in snap.heroes.items():
                if hk != "all-heroes":
                    totals[hk] = totals.get(hk, 0.0) + cnt.time_played

        for role in ("tank", "damage", "support"):
            if role in existing:
                continue
            role_heroes = [hk for hk, r in roles_map.items() if r == role]
            if not role_heroes:
                continue
            role_heroes.sort(key=lambda hk: totals.get(hk, 0.0), reverse=True)
            self.set_preferred_hero(user_id, role, role_heroes[0])

    # --- Снимки карьеры ---
    def save_snapshot(self, user_id: int, gamemode: str, snap: CareerSnapshot):
        payload = {k: asdict(v) for k, v in snap.heroes.items()}
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO career_snapshots (user_id, gamemode, snapshot_json, taken_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, gamemode) DO UPDATE SET
                    snapshot_json=excluded.snapshot_json, taken_at=excluded.taken_at
                """,
                (user_id, gamemode, json.dumps(payload), snap.taken_at),
            )

    def record_poll_update(
        self,
        user_id: int,
        gamemode: str,
        deltas: Dict[str, HeroCounters],
        bucket_updates: Dict[str, BucketState],
        closed_observations: List[Tuple[str, ObservationRecord]],
        snap: CareerSnapshot,
        now_ts: int,
    ):
        """Commit one poll result atomically.

        Buckets, observations, the active session and the career snapshot are
        one logical update.  Keeping them in one SQLite transaction prevents a
        process restart from replaying or losing a delta on the next poll.
        """
        all_h = deltas.get("all-heroes", HeroCounters())
        payload = {k: asdict(v) for k, v in snap.heroes.items()}
        with self._conn() as conn:
            for hk, b in bucket_updates.items():
                conn.execute(
                    """
                    INSERT INTO observation_buckets
                    (user_id, gamemode, hero_key, time_sec, deaths, eliminations, damage, healing)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, gamemode, hero_key) DO UPDATE SET
                        time_sec=excluded.time_sec, deaths=excluded.deaths,
                        eliminations=excluded.eliminations, damage=excluded.damage,
                        healing=excluded.healing
                    """,
                    (user_id, gamemode, hk, b.time_sec, b.deaths, b.eliminations, b.damage, b.healing),
                )

            for hk, obs in closed_observations:
                conn.execute(
                    """
                    INSERT INTO observations
                    (user_id, gamemode, hero_key, output_10m, deaths_10m, eliminations_10m, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, gamemode, hk, obs.output_10m, obs.deaths_10m, obs.eliminations_10m, obs.created_at),
                )

            conn.execute(
                """
                INSERT INTO active_sessions
                (user_id, gamemode, started_at, last_change_at, games_played, games_won, games_lost)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, gamemode) DO UPDATE SET
                    last_change_at=excluded.last_change_at,
                    games_played=active_sessions.games_played + excluded.games_played,
                    games_won=active_sessions.games_won + excluded.games_won,
                    games_lost=active_sessions.games_lost + excluded.games_lost
                """,
                (user_id, gamemode, now_ts, now_ts, all_h.games_played, all_h.games_won, all_h.games_lost),
            )

            for hk, cnt in deltas.items():
                if hk == "all-heroes" or (cnt.time_played <= 0 and cnt.games_played <= 0):
                    continue
                conn.execute(
                    """
                    INSERT INTO session_heroes
                    (user_id, gamemode, hero_key, time_sec, deaths, eliminations, damage, healing,
                     games_played, games_won, games_lost)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, gamemode, hero_key) DO UPDATE SET
                        time_sec=session_heroes.time_sec + excluded.time_sec,
                        deaths=session_heroes.deaths + excluded.deaths,
                        eliminations=session_heroes.eliminations + excluded.eliminations,
                        damage=session_heroes.damage + excluded.damage,
                        healing=session_heroes.healing + excluded.healing,
                        games_played=session_heroes.games_played + excluded.games_played,
                        games_won=session_heroes.games_won + excluded.games_won,
                        games_lost=session_heroes.games_lost + excluded.games_lost
                    """,
                    (
                        user_id,
                        gamemode,
                        hk,
                        cnt.time_played,
                        cnt.deaths,
                        cnt.eliminations,
                        cnt.hero_damage_done,
                        cnt.healing_done,
                        cnt.games_played,
                        cnt.games_won,
                        cnt.games_lost,
                    ),
                )

            conn.execute(
                """
                INSERT INTO career_snapshots (user_id, gamemode, snapshot_json, taken_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, gamemode) DO UPDATE SET
                    snapshot_json=excluded.snapshot_json, taken_at=excluded.taken_at
                """,
                (user_id, gamemode, json.dumps(payload), snap.taken_at),
            )

    def get_snapshot(self, user_id: int, gamemode: str) -> Optional[CareerSnapshot]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT snapshot_json, taken_at FROM career_snapshots WHERE user_id = ? AND gamemode = ?",
                (user_id, gamemode),
            ).fetchone()
        if not row:
            return None
        raw = json.loads(row[0])
        heroes = {k: HeroCounters(**v) for k, v in raw.items()}
        return CareerSnapshot(taken_at=row[1], heroes=heroes)

    # --- Вёдра и наблюдения ---
    def get_bucket(self, user_id: int, gamemode: str, hero_key: str) -> BucketState:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT time_sec, deaths, eliminations, damage, healing
                FROM observation_buckets
                WHERE user_id = ? AND gamemode = ? AND hero_key = ?
                """,
                (user_id, gamemode, hero_key),
            ).fetchone()
        if not row:
            return BucketState()
        return BucketState(time_sec=row[0], deaths=row[1], eliminations=row[2], damage=row[3], healing=row[4])

    def save_bucket(self, user_id: int, gamemode: str, hero_key: str, b: BucketState):
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO observation_buckets (user_id, gamemode, hero_key, time_sec, deaths, eliminations, damage, healing)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, gamemode, hero_key) DO UPDATE SET
                    time_sec=excluded.time_sec, deaths=excluded.deaths, eliminations=excluded.eliminations,
                    damage=excluded.damage, healing=excluded.healing
                """,
                (user_id, gamemode, hero_key, b.time_sec, b.deaths, b.eliminations, b.damage, b.healing),
            )

    def insert_observation(self, user_id: int, gamemode: str, hero_key: str, obs: ObservationRecord):
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO observations (user_id, gamemode, hero_key, output_10m, deaths_10m, eliminations_10m, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, gamemode, hero_key, obs.output_10m, obs.deaths_10m, obs.eliminations_10m, obs.created_at),
            )

    def get_observations(
        self, user_id: int, gamemode: str, hero_key: str, limit: int = config.OBS_WINDOW
    ) -> List[ObservationRecord]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT output_10m, deaths_10m, eliminations_10m, created_at
                FROM observations
                WHERE user_id = ? AND gamemode = ? AND hero_key = ?
                ORDER BY id DESC LIMIT ?
                """,
                (user_id, gamemode, hero_key, limit),
            ).fetchall()
        return [
            ObservationRecord(output_10m=r[0], deaths_10m=r[1], eliminations_10m=r[2], created_at=r[3])
            for r in rows
        ]

    # --- Сессии ---
    def add_session_delta(self, user_id: int, gamemode: str, deltas: Dict[str, HeroCounters], now_ts: int):
        all_h = deltas.get("all-heroes", HeroCounters())
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO active_sessions (user_id, gamemode, started_at, last_change_at, games_played, games_won, games_lost)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, gamemode) DO UPDATE SET
                    last_change_at=excluded.last_change_at,
                    games_played=active_sessions.games_played + excluded.games_played,
                    games_won=active_sessions.games_won + excluded.games_won,
                    games_lost=active_sessions.games_lost + excluded.games_lost
                """,
                (user_id, gamemode, now_ts, now_ts, all_h.games_played, all_h.games_won, all_h.games_lost),
            )
            for hk, cnt in deltas.items():
                if hk == "all-heroes" or (cnt.time_played <= 0 and cnt.games_played <= 0):
                    continue
                conn.execute(
                    """
                    INSERT INTO session_heroes (user_id, gamemode, hero_key, time_sec, deaths, eliminations, damage, healing, games_played, games_won, games_lost)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, gamemode, hero_key) DO UPDATE SET
                        time_sec=session_heroes.time_sec + excluded.time_sec,
                        deaths=session_heroes.deaths + excluded.deaths,
                        eliminations=session_heroes.eliminations + excluded.eliminations,
                        damage=session_heroes.damage + excluded.damage,
                        healing=session_heroes.healing + excluded.healing,
                        games_played=session_heroes.games_played + excluded.games_played,
                        games_won=session_heroes.games_won + excluded.games_won,
                        games_lost=session_heroes.games_lost + excluded.games_lost
                    """,
                    (user_id, gamemode, hk, cnt.time_played, cnt.deaths, cnt.eliminations, cnt.hero_damage_done, cnt.healing_done, cnt.games_played, cnt.games_won, cnt.games_lost),
                )

    def get_active_session(self, user_id: int, gamemode: str) -> Optional[Tuple[ dict, Dict[str, HeroCounters] ]]:
        with self._conn() as conn:
            s_row = conn.execute(
                """
                SELECT started_at, last_change_at, games_played, games_won, games_lost, last_viewed_games
                FROM active_sessions WHERE user_id = ? AND gamemode = ?
                """,
                (user_id, gamemode),
            ).fetchone()
            if not s_row:
                return None
            h_rows = conn.execute(
                """
                SELECT hero_key, time_sec, deaths, eliminations, damage, healing,
                       COALESCE(games_played, 0), COALESCE(games_won, 0), COALESCE(games_lost, 0)
                FROM session_heroes WHERE user_id = ? AND gamemode = ?
                """,
                (user_id, gamemode),
            ).fetchall()

        meta = {
            "started_at": s_row[0],
            "last_change_at": s_row[1],
            "games_played": s_row[2],
            "games_won": s_row[3],
            "games_lost": s_row[4],
            "last_viewed_games": s_row[5] if len(s_row) > 5 else 0,
        }
        heroes = {
            r[0]: HeroCounters(
                time_played=r[1],
                deaths=r[2],
                eliminations=r[3],
                hero_damage_done=r[4],
                healing_done=r[5],
                games_played=r[6] if len(r) > 6 else 0,
                games_won=r[7] if len(r) > 7 else 0,
                games_lost=r[8] if len(r) > 8 else 0,
            )
            for r in h_rows
        }
        return meta, heroes

    def mark_session_viewed(self, user_id: int, gamemode: str, games_count: int):
        with self._conn() as conn:
            conn.execute(
                "UPDATE active_sessions SET last_viewed_games = ? WHERE user_id = ? AND gamemode = ?",
                (games_count, user_id, gamemode),
            )

    def clear_active_session(self, user_id: int, gamemode: str):
        with self._conn() as conn:
            conn.execute("DELETE FROM active_sessions WHERE user_id = ? AND gamemode = ?", (user_id, gamemode))
            conn.execute("DELETE FROM session_heroes WHERE user_id = ? AND gamemode = ?", (user_id, gamemode))

    def archive_active_session(self, user_id: int, gamemode: str, ended_at: Optional[int] = None) -> Optional[int]:
        """
        Переносит завершенную активную сессию в историю session_history и очищает её из active_sessions.
        Возвращает ID сохраненной записи истории.
        """
        active = self.get_active_session(user_id, gamemode)
        if not active:
            return None

        meta, heroes = active
        now_ts = ended_at or int(time.time())
        duration_sec = sum(c.time_played for c in heroes.values())
        tot_elim = sum(c.eliminations for c in heroes.values())
        tot_deaths = sum(c.deaths for c in heroes.values())
        tot_damage = sum(c.hero_damage_done for c in heroes.values())
        tot_healing = sum(c.healing_done for c in heroes.values())

        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO session_history
                (user_id, gamemode, started_at, ended_at, duration_sec, games_played, games_won, games_lost,
                 eliminations, deaths, damage, healing)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    gamemode,
                    meta["started_at"],
                    now_ts,
                    duration_sec,
                    meta["games_played"],
                    meta["games_won"],
                    meta["games_lost"],
                    tot_elim,
                    tot_deaths,
                    tot_damage,
                    tot_healing,
                ),
            )
            sess_id = cur.lastrowid
            for hk, cnt in heroes.items():
                if cnt.time_played <= 0 and cnt.games_played <= 0:
                    continue
                conn.execute(
                    """
                    INSERT INTO session_history_heroes
                    (session_id, hero_key, time_sec, eliminations, deaths, damage, healing, games_played, games_won, games_lost)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (sess_id, hk, cnt.time_played, cnt.eliminations, cnt.deaths, cnt.hero_damage_done, cnt.healing_done, cnt.games_played, cnt.games_won, cnt.games_lost),
                )

            # Keep archiving and removal in one transaction.  If the process
            # stops after the INSERT but before a second transaction deletes
            # the active rows, the next poll would archive the same session a
            # second time and duplicate the weekly totals.
            conn.execute(
                "DELETE FROM active_sessions WHERE user_id = ? AND gamemode = ?",
                (user_id, gamemode),
            )
            conn.execute(
                "DELETE FROM session_heroes WHERE user_id = ? AND gamemode = ?",
                (user_id, gamemode),
            )
        return sess_id

    def get_history_sessions_since(
        self,
        user_id: int,
        since_ts: int,
        gamemode: Optional[str] = None,
        until_ts: Optional[int] = None,
    ) -> List[Tuple[dict, Dict[str, HeroCounters]]]:
        """
        Возвращает список завершенных сессий из истории начиная с since_ts.
        Каждый элемент: (meta_dict, heroes_dict).
        """
        with self._conn() as conn:
            # Sessions are attributed to the calendar week in which they
            # started.  An upper bound is essential for reports generated on
            # Monday: without it, Monday's sessions leak into the previous
            # week's report.
            if until_ts is None:
                time_clause = "started_at >= ?"
                time_params = (since_ts,)
            else:
                time_clause = "started_at >= ? AND started_at <= ?"
                time_params = (since_ts, until_ts)

            if gamemode:
                rows = conn.execute(
                    """
                    SELECT id, gamemode, started_at, ended_at, duration_sec, games_played, games_won, games_lost,
                           eliminations, deaths, damage, healing
                    FROM session_history
                    WHERE user_id = ? AND gamemode = ? AND """ + time_clause + """
                    ORDER BY ended_at ASC
                    """,
                    (user_id, gamemode, *time_params),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, gamemode, started_at, ended_at, duration_sec, games_played, games_won, games_lost,
                           eliminations, deaths, damage, healing
                    FROM session_history
                    WHERE user_id = ? AND """ + time_clause + """
                    ORDER BY ended_at ASC
                    """,
                    (user_id, *time_params),
                ).fetchall()

            result = []
            for r in rows:
                sid = r[0]
                meta = {
                    "id": sid,
                    "gamemode": r[1],
                    "started_at": r[2],
                    "ended_at": r[3],
                    "duration_sec": r[4],
                    "games_played": r[5],
                    "games_won": r[6],
                    "games_lost": r[7],
                    "eliminations": r[8],
                    "deaths": r[9],
                    "damage": r[10],
                    "healing": r[11],
                }
                h_rows = conn.execute(
                    """
                    SELECT hero_key, time_sec, eliminations, deaths, damage, healing,
                           COALESCE(games_played, 0), COALESCE(games_won, 0), COALESCE(games_lost, 0)
                    FROM session_history_heroes
                    WHERE session_id = ?
                    """,
                    (sid,),
                ).fetchall()
                heroes = {
                    hr[0]: HeroCounters(
                        time_played=hr[1],
                        eliminations=hr[2],
                        deaths=hr[3],
                        hero_damage_done=hr[4],
                        healing_done=hr[5],
                        games_played=hr[6] if len(hr) > 6 else 0,
                        games_won=hr[7] if len(hr) > 7 else 0,
                        games_lost=hr[8] if len(hr) > 8 else 0,
                    )
                    for hr in h_rows
                }
                result.append((meta, heroes))
        return result
