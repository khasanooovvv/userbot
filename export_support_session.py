import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


async def main():
    api_id = int(os.environ["API_ID"])
    api_hash = os.environ["API_HASH"]
    phone = os.environ.get("SUPPORT_PHONE_NUMBER", "").strip()
    if not phone:
        raise RuntimeError(".env faylida SUPPORT_PHONE_NUMBER ni kiriting")

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.start(phone=phone)
    print("\nSUPPORT_SESSION_STRING quyidagicha (hech kimga yubormang):\n")
    print(StringSession.save(client.session))
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
