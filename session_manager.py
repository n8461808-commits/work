"""
Сопоставление .session файлов с прокси (биндинг прокси-на-сессию).

Каждой сессии назначается уникальный прокси по порядку. Если прокси меньше,
чем сессий — лишние сессии будут пропущены (чтобы не нарушать правило
«один прокси = одна сессия»). Это поведение можно изменить через allow_reuse.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from proxy_manager import ProxyTuple

log = logging.getLogger("session_manager")


@dataclass
class SessionBinding:
    """Связка: путь к .session файлу + назначенный ему прокси (None = напрямую)."""
    name: str                      # имя аккаунта (имя файла без расширения)
    session_path: Path             # полный путь к .session
    proxy: Optional[ProxyTuple]    # назначенный прокси или None


def discover_sessions(sessions_dir: Path) -> List[Path]:
    """Найти все .session файлы в папке (отсортированы для детерминизма)."""
    if not sessions_dir.exists():
        raise FileNotFoundError(f"Папка с сессиями не найдена: {sessions_dir}")
    sessions = sorted(sessions_dir.glob("*.session"))
    if not sessions:
        raise ValueError(f"В папке {sessions_dir} нет ни одного .session файла.")
    return sessions


def bind_proxies(
    sessions: List[Path],
    proxies: List[ProxyTuple],
    allow_reuse: bool = False,
) -> List[SessionBinding]:
    """
    Привязать к каждой сессии уникальный прокси.

    allow_reuse=False (по умолчанию): строго один прокси на сессию; если прокси
    не хватает — лишние сессии отбрасываются с предупреждением.
    allow_reuse=True: прокси раздаются по кругу (round-robin).

    Особый случай: если прокси нет вообще (пустой список) — все сессии
    работают напрямую (proxy=None). Удобно для теста, но в бою не рекомендуется.
    """
    if not proxies:
        log.warning("Прокси не заданы — все сессии будут работать НАПРЯМУЮ (без прокси).")
        return [
            SessionBinding(name=p.stem, session_path=p, proxy=None)
            for p in sessions
        ]

    bindings: List[SessionBinding] = []

    for idx, session_path in enumerate(sessions):
        if idx >= len(proxies) and not allow_reuse:
            log.warning(
                "Прокси закончились — сессия %s пропущена (нет уникального прокси).",
                session_path.name,
            )
            continue

        proxy = proxies[idx % len(proxies)]
        bindings.append(
            SessionBinding(
                name=session_path.stem,
                session_path=session_path,
                proxy=proxy,
            )
        )

    log.info("Привязано прокси к сессиям: %d", len(bindings))
    return bindings
