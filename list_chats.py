import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


async def main():
    client = TelegramClient(
        str(BASE_DIR / "forwarder"),
        int(os.environ["API_ID"]),
        os.environ["API_HASH"],
    )
    await client.start(phone=os.environ["PHONE_NUMBER"])
    async for dialog in client.iter_dialogs():
        print(f"{dialog.id}\t{dialog.name}")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
