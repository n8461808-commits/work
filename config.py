"""
Центральная конфигурация проекта.

Все пути и параметры собраны здесь, чтобы их было удобно менять
без правки логики. Значения можно переопределять через переменные окружения.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- API-ключи Telegram (https://my.telegram.org) ---------------------------
# Один и тот же api_id/api_hash можно использовать для всех аккаунтов.
API_ID: int = int(os.getenv("TG_API_ID", "0"))
API_HASH: str = os.getenv("TG_API_HASH", "")

# --- Пути к файлам ----------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent

# Папка с .session файлами Telethon (по одному на аккаунт).
SESSIONS_DIR: Path = Path(os.getenv("SESSIONS_DIR", BASE_DIR / "sessions"))

# Файл с прокси: одна строка = один прокси, формат описан в proxy_manager.py.
PROXIES_FILE: Path = Path(os.getenv("PROXIES_FILE", BASE_DIR / "proxies.txt"))

# Файл со списком целевых user_id (по одному ID в строке).
TARGETS_FILE: Path = Path(os.getenv("TARGETS_FILE", BASE_DIR / "targets.txt"))

# --- Поведение / тайминги ---------------------------------------------------
# Базовая задержка между действиями одного аккаунта (секунды).
ACTION_DELAY: float = float(os.getenv("ACTION_DELAY", "2.0"))

# Сколько секунд «остудить» аккаунт после PeerFloodError, прежде чем
# отдать оставшиеся задачи (аккаунт выводится из работы на этот цикл).
PEER_FLOOD_COOLDOWN: int = int(os.getenv("PEER_FLOOD_COOLDOWN", "3600"))

# Если FloodWait требует паузу больше этого порога — аккаунт пропускает
# остаток задач, чтобы не висеть часами. 0 = ждать всегда.
MAX_FLOOD_WAIT: int = int(os.getenv("MAX_FLOOD_WAIT", "300"))

# Уровень логирования.
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
