"""
Создание .session файлов (один раз на каждый аккаунт).

Запуск интерактивный:
    python login.py

Скрипт спросит номер телефона, пришлёт код в Telegram, при необходимости
запросит пароль (двухфакторка) и сохранит готовую сессию в папку sessions/.
Эту сессию потом использует main.py — повторный логин не нужен.

Прокси для логина можно указать тем же форматом, что и в proxies.txt
(type:host:port[:user:pass]) — желательно логиниться с того же прокси,
с которого аккаунт потом будет работать.
"""
from __future__ import annotations

import asyncio

from telethon import TelegramClient

import config
from proxy_manager import _parse_line


async def main() -> None:
    if not config.API_ID or not config.API_HASH:
        raise SystemExit(
            "Сначала задайте TG_API_ID / TG_API_HASH "
            "(см. https://my.telegram.org)."
        )

    config.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    name = input("Имя сессии (латиницей, напр. acc1): ").strip()
    if not name:
        raise SystemExit("Пустое имя сессии.")

    proxy_raw = input(
        "Прокси для логина (type:host:port[:user:pass]) "
        "или Enter чтобы без прокси: "
    ).strip()
    proxy = _parse_line(proxy_raw) if proxy_raw else None

    session_path = config.SESSIONS_DIR / name
    client = TelegramClient(str(session_path), config.API_ID, config.API_HASH, proxy=proxy)

    # client.start() сам спросит номер, код и при необходимости пароль 2FA.
    await client.start()

    me = await client.get_me()
    print(f"\n✅ Готово! Авторизован как {me.first_name} (id={me.id})")
    print(f"   Файл сессии: {session_path}.session")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
