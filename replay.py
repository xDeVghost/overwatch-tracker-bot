"""
Режим воспроизведения JSON-снимков:
1) Если передано несколько файлов:
   /opt/owbot/venv/bin/python /opt/owbot/replay.py snap1.json snap2.json snap3.json
   Последовательно прогоняет снимки через движок и сохраняет карточку в /opt/owbot/replay_output.png.

2) Если передан один базовый файл (например, qp.json):
   /opt/owbot/venv/bin/python /opt/owbot/replay.py qp.json
   Генерирует из него цепочку синтетических шагов для проверки накопления наблюдений и рендера карточки.
"""
import copy
import json
import logging
import os
import sys
import tempfile

import config
from db import Database
from engine import compute_delta, select_output_metric_type, snapshots_equal, update_bucket_with_delta
from provider import parse_raw_career_json
from renderer import render_session_card
from bot import build_session_card_for_mode

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("replay")


def run_replay(json_paths: list[str], out_png: str = "/opt/owbot/replay_output.png"):
    tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    db = Database(tmp_db)
    user_id = 1
    btag = "ReplayUser-1234"
    mode = "quickplay"
    db.upsert_user(user_id, btag)

    raw_frames = []
    if len(json_paths) == 1:
        with open(json_paths[0], "r", encoding="utf-8") as f:
            base_raw = json.load(f)
        raw_frames.append(base_raw)
        # Строим 10 шагов из базового файла для проверки полного цикла (8+ наблюдений и сессия)
        curr = copy.deepcopy(base_raw)
        for step in range(1, 11):
            curr = copy.deepcopy(curr)
            all_g = curr.setdefault("all-heroes", {}).setdefault("game", {})
            all_g["games_played"] = int(all_g.get("games_played", 0)) + 1
            if step % 2 == 1:
                all_g["games_won"] = int(all_g.get("games_won", 0)) + 1
            else:
                all_g["games_lost"] = int(all_g.get("games_lost", 0)) + 1

            for hk in [k for k in curr.keys() if k != "all-heroes"][:2]:
                h_game = curr[hk].setdefault("game", {})
                h_comb = curr[hk].setdefault("combat", {})
                h_ass = curr[hk].setdefault("assists", {})
                h_game["time_played"] = float(h_game.get("time_played", 0)) + 650
                h_comb["deaths"] = float(h_comb.get("deaths", 0)) + (4 if step < 9 else 8)
                h_comb["hero_damage_done"] = float(h_comb.get("hero_damage_done", 0)) + (8200 if step < 9 else 9800)
                if float(h_ass.get("healing_done", 0)) > 0:
                    h_ass["healing_done"] = float(h_ass.get("healing_done", 0)) + 7500
            raw_frames.append(curr)
    else:
        for p in json_paths:
            with open(p, "r", encoding="utf-8") as f:
                raw_frames.append(json.load(f))

    roles_map, _ = db.get_heroes_maps()
    ts = 1_700_000_000

    for idx, raw in enumerate(raw_frames):
        ts += config.POLL_INTERVAL_SEC
        snap = parse_raw_career_json(raw, taken_at=ts)
        prev = db.get_snapshot(user_id, mode)
        if not prev:
            db.save_snapshot(user_id, mode, snap)
            db.auto_init_preferences(user_id, snap, None)
            logger.info(f"Step {idx}: baseline snapshot loaded ({len(snap.heroes)} heroes)")
            continue

        if snapshots_equal(prev, snap):
            logger.info(f"Step {idx}: identical snapshot skipped")
            continue

        deltas, is_reset = compute_delta(prev, snap)
        if is_reset or deltas is None:
            db.save_snapshot(user_id, mode, snap)
            logger.warning(f"Step {idx}: negative delta reset")
            continue

        for hk, h_delta in deltas.items():
            if hk == "all-heroes" or h_delta.time_played <= 0:
                continue
            role = roles_map.get(hk, "damage")
            m_type = select_output_metric_type(role, snap.heroes.get(hk), h_delta.healing_done)
            bucket = db.get_bucket(user_id, mode, hk)
            new_b, obs = update_bucket_with_delta(bucket, h_delta, m_type, config.OBS_SEC, ts)
            db.save_bucket(user_id, mode, hk, new_b)
            if obs:
                db.insert_observation(user_id, mode, hk, obs)

        # Записываем в сессию последние шаги
        if idx >= max(1, len(raw_frames) - 3):
            db.add_session_delta(user_id, mode, deltas, ts)

        db.save_snapshot(user_id, mode, snap)

    # Переключаем глобальный db в bot для сборки карточки
    import bot as bot_module
    bot_module.db = db
    card, total_sec = build_session_card_for_mode(user_id, btag, mode)
    if card:
        png = render_session_card(card)
        with open(out_png, "wb") as f:
            f.write(png)
        logger.info(f"REPLAY_SUCCESS: card saved to {out_png} (session_sec={total_sec:.0f}s)")
    else:
        logger.warning(f"REPLAY_NO_CARD: total_sec={total_sec:.0f}s")

    import gc
    del db
    gc.collect()
    try:
        os.remove(tmp_db)
    except PermissionError:
        pass


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python replay.py <qp.json> [snap2.json ...]")
        sys.exit(1)
    run_replay(sys.argv[1:])
