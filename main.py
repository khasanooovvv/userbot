import asyncio
import logging
import os
import re
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


def amount_matches(message_text: str, allowed_amounts: set[str]) -> bool:
    candidates = re.findall(r"(?<!\d)(\d{1,3}(?:[ ,.\u00a0]\d{3})+|\d+)(?!\d)", message_text)
    return any(re.sub(r"\D", "", item) in allowed_amounts for item in candidates)


async def main() -> None:
    try:
        api_id = int(required("API_ID"))
    except ValueError as exc:
        raise RuntimeError("API_ID raqam bo'lishi kerak") from exc

    api_hash = required("API_HASH")
    phone = required("PHONE_NUMBER")
    source_values = os.getenv("SOURCE_CHATS", os.getenv("SOURCE_CHAT", ""))
    if not source_values.strip():
        raise RuntimeError(".env faylida SOURCE_CHATS ko'rsatilmagan")
    sources = [chat_value(item) for item in source_values.split(",") if item.strip()]
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
    allowed_amounts = {
        re.sub(r"\D", "", item)
        for item in os.getenv("FILTER_AMOUNTS", "").split(",")
        if re.sub(r"\D", "", item)
    }
    card_last4 = re.sub(r"\D", "", os.getenv("FILTER_CARD_LAST4", ""))
    humo_source = os.getenv("HUMO_SOURCE", "@HUMOcardbot").strip().lower()
    humo_card_last4 = re.sub(r"\D", "", os.getenv("HUMO_CARD_LAST4", "9963"))
    required_texts = [
        item.strip().lower()
        for item in os.getenv("FILTER_REQUIRED_TEXT", "🟢,➕").split(",")
        if item.strip()
    ]

    session_string = os.getenv("SESSION_STRING", "").strip()
    session = StringSession(session_string) if session_string else str(BASE_DIR / "forwarder")
    client = TelegramClient(session, api_id, api_hash)
    if session_string:
        await client.connect()
        if not await client.is_user_authorized():
            raise RuntimeError("SESSION_STRING yaroqsiz yoki muddati tugagan")
    else:
        await client.start(phone=phone)

    source_entities = [await client.get_entity(item) for item in sources]
    destination_entities = [await client.get_entity(item) for item in destinations]
    logger.info("Kuzatilayotgan manbalar soni: %d", len(source_entities))
    logger.info("Qabul qiluvchilar soni: %d | rejim: %s", len(destination_entities), mode)

    @client.on(events.NewMessage(chats=source_entities))
    async def forward_new_message(event):
        message = event.message
        text = message.raw_text or ""
        is_humo = (getattr(event.chat, "username", "") or "").lower() == humo_source.lstrip("@")
        if allowed_amounts and not amount_matches(text, allowed_amounts):
            logger.info("Xabar %s o'tkazib yuborildi: summa mos emas", message.id)
            return
        if is_humo:
            if "➕" not in text or humo_card_last4 not in text:
                logger.info("Xabar %s o'tkazib yuborildi: HUMO filtri mos emas", message.id)
                return
        if not is_humo and card_last4 and card_last4 not in text:
            logger.info("Xabar %s o'tkazib yuborildi: karta mos emas", message.id)
            return
        if not is_humo and required_texts and not any(item in text.lower() for item in required_texts):
            logger.info("Xabar %s o'tkazib yuborildi: xabar turi mos emas", message.id)
            return
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
