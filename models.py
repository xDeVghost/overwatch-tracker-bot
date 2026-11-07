from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class HeroCounters:
    time_played: float = 0.0
    deaths: float = 0.0
    eliminations: float = 0.0
    hero_damage_done: float = 0.0
    healing_done: float = 0.0
    games_played: int = 0
    games_won: int = 0
    games_lost: int = 0


@dataclass
class CareerSnapshot:
    taken_at: int
    heroes: Dict[str, HeroCounters] = field(default_factory=dict)


@dataclass
class BucketState:
    time_sec: float = 0.0
    deaths: float = 0.0
    eliminations: float = 0.0
    damage: float = 0.0
    healing: float = 0.0


@dataclass
class ObservationRecord:
    output_10m: float
    deaths_10m: float
    eliminations_10m: float = 0.0
    created_at: int = 0


@dataclass
class MetricScaleResult:
    metric_type: str          # "damage" | "healing" | "deaths" | "eliminations"
    title: str                # "Урон" | "Хил" | "Смерти" | "Убийства"
    session_val: float
    norm_val: float
    band_low: float
    band_high: float
    status: str               # "better" | "usual" | "worse" | "no_norm"
    color: str                # "green" | "gray" | "red"
    pct_diff: Optional[int]
    label_text: str           # Человекочитаемая подпись без мат. терминов
    pos_norm: float           # Координата точки на шкале [0.0 .. 1.0], вправо всегда лучше
    clamped: Optional[str]    # "left" | "right" | None (если точка за краем шкалы -> стрелка)
    show_scale: bool          # False, если норма == 0


@dataclass
class HeroCardBlock:
    role: str                 # "tank" | "damage" | "support"
    role_title: str           # "ТАНК" | "УРОН" | "ПОДДЕРЖКА"
    hero_key: str
    hero_name: str
    time_min: int
    is_fallback: bool         # True -> пометка «не основной»
    has_verdict: bool
    verdict_text: str         # «лучше обычного» | «хуже обычного» | «как обычно» | «по-разному» | «рано судить...»
    early_reason: Optional[str] = None
    career_ref_text: Optional[str] = None
    eliminations: float = 0.0
    eliminations_10m: float = 0.0
    output_scale: Optional[MetricScaleResult] = None
    deaths_scale: Optional[MetricScaleResult] = None
    eliminations_scale: Optional[MetricScaleResult] = None


@dataclass
class OtherHeroItem:
    hero_key: str
    hero_name: str
    time_min: int
    eliminations: float = 0.0


@dataclass
class RoleRankProgress:
    role: str                 # "tank" | "damage" | "support"
    role_title: str           # "ТАНК" | "УРОН" | "ПОДДЕРЖКА"
    division: str             # "bronze" | "silver" | "gold" | "platinum" | "diamond" | "master" | "grandmaster" | "champion" | "unranked"
    division_title: str       # "Платина", "Золото"
    tier: int                 # 1..5 (1 - высший в дивизионе)
    progress_pct: int = 50    # Прогресс внутри дивизиона 0..100%
    delta_text: Optional[str] = None  # "▲ +1 ранг" или "▲ 3-1 в сессии"


@dataclass
class SessionCardData:
    player_name: str
    gamemode: str             # "quickplay" | "competitive"
    mode_title: str           # "Быстрая игра" | "Соревновательный"
    duration_min: int
    games_played: int
    games_won: int
    games_lost: int
    role_blocks: List[HeroCardBlock]
    other_heroes: List[OtherHeroItem]
    total_eliminations: int = 0
    total_deaths: int = 0
    kd_val: float = 0.0
    kd_status: str = "usual"  # "better" | "worse" | "usual"
    kd_diff_pct: Optional[int] = None
    kd_label: str = ""
    player_avatar_path: Optional[str] = None
    rank_progress: Optional[List[RoleRankProgress]] = None
    season_number: Optional[int] = None
    language: str = "ru"


# ==================== МОДЕЛИ НЕДЕЛЬНОГО ОТЧЕТА ====================
@dataclass
class DailyMatchStats:
    day_name: str             # "ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"
    date_str: str             # "26.10"
    games_played: int = 0
    games_won: int = 0
    games_lost: int = 0
    time_sec: float = 0.0
    winrate_pct: int = 0
    is_best_day: bool = False


@dataclass
class HeroWeeklyStats:
    hero_key: str
    hero_name: str
    role: str
    time_sec: float = 0.0
    games_played: int = 0
    games_won: int = 0
    games_lost: int = 0
    eliminations_10m: float = 0.0
    deaths_10m: float = 0.0
    damage_10m: float = 0.0
    healing_10m: float = 0.0


@dataclass
class WeeklyReportData:
    player_name: str
    gamemode: str
    mode_title: str
    period_title: str         # "Неделя 26 окт — 1 ноя"
    total_matches: int = 0
    total_wins: int = 0
    total_losses: int = 0
    winrate_pct: int = 0
    total_time_sec: float = 0.0
    sessions_count: int = 0
    days: List[DailyMatchStats] = field(default_factory=list)
    top_heroes: List[HeroWeeklyStats] = field(default_factory=list)
    best_day_title: str = "—"
    hero_of_the_week: str = "—"
    longest_session_str: str = "—"
    player_avatar_path: Optional[str] = None
    rank_progress: Optional[List[RoleRankProgress]] = None
    season_number: Optional[int] = None
    language: str = "ru"
