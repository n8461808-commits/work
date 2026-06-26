"""
Чтение прокси и преобразование их в формат, понятный Telethon.

Формат строки в proxies.txt (поля разделяются двоеточием):

    type:host:port
    type:host:port:user:pass

где type — один из: http, socks5, socks4.

Примеры:
    socks5:1.2.3.4:1080:login:password
    http:10.0.0.1:8080
    # строки, начинающиеся с '#', и пустые строки игнорируются
"""
from __future__ import annotations

import socks  # из пакета PySocks

from pathlib import Path
from typing import List, Tuple

# Telethon принимает прокси как кортеж в стиле PySocks:
#   (proxy_type, addr, port, rdns, username, password)
ProxyTuple = Tuple[int, str, int, bool, str | None, str | None]

_PROXY_TYPES = {
    "socks5": socks.SOCKS5,
    "socks4": socks.SOCKS4,
    "http": socks.HTTP,
    "https": socks.HTTP,
}


def _parse_line(line: str) -> ProxyTuple:
    parts = line.split(":")
    if len(parts) not in (3, 5):
        raise ValueError(
            f"Неверный формат прокси: {line!r}. "
            "Ожидается type:host:port или type:host:port:user:pass"
        )

    proxy_type_raw, host, port = parts[0].strip().lower(), parts[1].strip(), parts[2].strip()
    if proxy_type_raw not in _PROXY_TYPES:
        raise ValueError(f"Неизвестный тип прокси: {proxy_type_raw!r} в строке {line!r}")

    username = parts[3].strip() if len(parts) == 5 else None
    password = parts[4].strip() if len(parts) == 5 else None

    # rdns=True — резолвить имена на стороне прокси (важно для анонимности).
    return (_PROXY_TYPES[proxy_type_raw], host, int(port), True, username, password)


def load_proxies(path: Path) -> List[ProxyTuple]:
    """
    Загрузить прокси из файла. Если файла нет или он пустой — вернуть []
    (тогда сессии работают напрямую, без прокси).
    """
    if not path.exists():
        return []

    proxies: List[ProxyTuple] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        proxies.append(_parse_line(line))

    return proxies
