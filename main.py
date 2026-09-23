import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("forwarder")


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f".env faylida {name} ko'rsatilmagan")
    return value


def chat_value(value: str):
    value = value.strip()
    try:
        return int(value)
    except ValueError:
        return value


async def main() -> None:
    try:
        api_id = int(required("API_ID"))
    except ValueError as exc:
        raise RuntimeError("API_ID raqam bo'lishi kerak") from exc

    api_hash = required("API_HASH")
    phone = required("PHONE_NUMBER")
    source = chat_value(required("SOURCE_CHAT"))
    destinations = [
        chat_value(item)
        for item in required("DESTINATION_CHATS").split(",")
        if item.strip()
    ]
    if not destinations:
        raise RuntimeError("Kamida bitta DESTINATION_CHATS kerak")

    mode = os.getenv("MODE", "forward").strip().lower()
    if mode not in {"forward", "copy"}:
        raise RuntimeError("MODE faqat forward yoki copy bo'lishi mumkin")

    session_string = os.getenv("SESSION_STRING", "").strip()
    session = StringSession(session_string) if session_string else str(BASE_DIR / "forwarder")
    client = TelegramClient(session, api_id, api_hash)
    if session_string:
        await client.connect()
        if not await client.is_user_authorized():
            raise RuntimeError("SESSION_STRING yaroqsiz yoki muddati tugagan")
    else:
        await client.start(phone=phone)

    source_entity = await client.get_entity(source)
    destination_entities = [await client.get_entity(item) for item in destinations]
    logger.info("Kuzatilmoqda: %s", getattr(source_entity, "title", source))
    logger.info("Qabul qiluvchilar soni: %d | rejim: %s", len(destination_entities), mode)

    @client.on(events.NewMessage(chats=source_entity))
    async def forward_new_message(event):
        message = event.message
        for destination in destination_entities:
            try:
                if mode == "copy":
                    await client.send_message(destination, message)
                else:
                    await client.forward_messages(destination, message)
                logger.info("Xabar %s -> %s yuborildi", message.id, getattr(destination, "title", destination))
            except Exception:
                logger.exception("Xabar %s yuborilmadi", message.id)

    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("To'xtatildi")
