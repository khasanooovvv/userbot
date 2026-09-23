import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


async def main():
    client = TelegramClient(
        str(BASE_DIR / "forwarder"),
        int(os.environ["API_ID"]),
        os.environ["API_HASH"],
    )
    await client.connect()
    if not await client.is_user_authorized():
        print("Avval main.py orqali lokal login qiling.")
        await client.disconnect()
        return
    print("SESSION_STRING quyidagicha:")
    print(StringSession.save(client.session))
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
