import asyncio
import difflib
import logging
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from openai import AsyncOpenAI


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


def needs_operator(text: str) -> bool:
    keywords = (
        "muammo", "muammoli", "shikoyat", "operator", "yordam", "tushmadi", "kelmadi",
        "ошибка", "проблем", "жалоб", "оператор", "помогите", "не приш", "не поступ",
        "мәселе", "шағым", "оператор", "көмек", "түспеді", "келмеді",
        "көйгөй", "даттануу", "оператор", "жардам", "түшкөн жок", "келген жок",
    )
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def is_problem_intent(text: str) -> bool:
    keywords = (
        "bot ishlamay", "bot ishlamadi", "kamchilik", "xato", "muammo", "shikoyat",
        "to'lov", "tolov", "pul tushmadi", "hisoblanmadi", "obuna ishlamay",
        "не работает", "ошибка", "проблем", "оплата", "платеж", "деньги не",
        "мәселе", "төлем", "ақша түсп", "көйгөй", "төлөм", "акча түшп",
    )
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def is_xsnot_related(text: str) -> bool:
    keywords = (
        "xsnot", "bot", "random", "chat", "profil", "profile", "match", "obuna", "подпис",
        "gold", "silver", "referral", "referal", "to'lov", "tolov", "платеж", "оплата",
        "chek", "скрин", "uzcard", "humo", "paynet", "report", "shikoyat", "muammo",
        "yordam", "ishlam", "ishlay", "ochil", "kirmay", "ro'yxat", "registr", "premium",
        "аккаунт", "профил", "чат", "рандом", "реферал", "помощь", "ошибка", "не работает",
    )
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


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

    support_task = None
    support_session = os.getenv("SUPPORT_SESSION_STRING", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    support_chat = os.getenv("SUPPORT_CHAT", "support").strip()
    if support_session and openai_key:
        support_client = TelegramClient(StringSession(support_session), api_id, api_hash)
        await support_client.connect()
        if not await support_client.is_user_authorized():
            raise RuntimeError("SUPPORT_SESSION_STRING yaroqsiz yoki muddati tugagan")
        ai = AsyncOpenAI(api_key=openai_key)
        support_state = {}
        operator_entities = [
            await support_client.get_entity(item.strip())
            for item in os.getenv("SUPPORT_OPERATORS", "@sherzodkh,@the_pasibo").split(",")
            if item.strip()
        ]
        operator_ids = {entity.id for entity in operator_entities}
        operator_reply_map = {}
        muted_until = {}

        async def notify_operators(event, text, title="Yangi support murojaati"):
            sender = await event.get_sender()
            username = getattr(sender, "username", None)
            profile = (
                f"<a href=\"https://t.me/{username}\">@{username}</a>"
                if username
                else f"<a href=\"tg://user?id={event.sender_id}\">Mijoz profilini ochish</a>"
            )
            for operator in operator_entities:
                sent = await support_client.send_message(
                    operator,
                    f"📩 <b>{title}</b>\n👤 Mijoz: {profile}\n\n{text}",
                    parse_mode="html",
                )
                operator_reply_map[sent.id] = event.sender_id

        @support_client.on(events.NewMessage(incoming=True))
        async def relay_operator_reply(event):
            if not event.is_private or event.sender_id not in operator_ids or not event.is_reply:
                return
            reply_to = await event.get_reply_message()
            customer_id = operator_reply_map.get(reply_to.id if reply_to else None)
            if not customer_id:
                return
            text = (event.raw_text or "").strip()
            mute_match = re.fullmatch(r"/mute\s+([0-9]{1,2})", text.lower())
            if mute_match:
                hours = int(mute_match.group(1))
                if 1 <= hours <= 24:
                    muted_until[customer_id] = time.time() + hours * 3600
                    await event.reply(f"Mijoz {hours} soatga mute qilindi.")
                else:
                    await event.reply("/mute uchun 1 dan 24 gacha soat kiriting.")
                return
            if text.lower() == "/unmute":
                muted_until.pop(customer_id, None)
                await event.reply("Mijoz mute holatidan chiqarildi.")
                return
            if text:
                await support_client.send_message(customer_id, text)
                logger.info("Operator javobi mijozga yuborildi: %s", customer_id)
        support_prompt = os.getenv(
            "SUPPORT_SYSTEM_PROMPT",
            "Sen xsnot Telegram botining support yordamchisisan. Foydalanuvchi qaysi tilda yozsa, o'sha tilda javob ber: o'zbek, rus, qozoq yoki qirg'iz. xsnot botida random chat, anonim yoki ochiq profil, yosh/shahar filtrlari, to'lov va obuna, Gold/Silver, referral, profil, report va xavfsizlik funksiyalari bor. Shu bot bo'yicha qisqa, muloyim va amaliy yordam ber. To'lovni o'zing tasdiqlangan deb va'da qilma. Bilmagan yoki texnik muammolarni operatorga yuborilishini ayt.",
        )

        @support_client.on(events.NewMessage(incoming=True))
        async def answer_support(event):
            if not event.is_private:
                return
            if event.sender_id in operator_ids:
                return
            if muted_until.get(event.sender_id, 0) > time.time():
                return
            if event.sender_id in muted_until:
                muted_until.pop(event.sender_id, None)
            text = (event.raw_text or "").strip()
            if not text:
                return
            logger.info("Support xabari qabul qilindi: %s", event.sender_id)
            try:
                state = support_state.setdefault(event.sender_id, {"last": "", "repeats": 0})
                normalized = " ".join(text.lower().split())
                similarity = difflib.SequenceMatcher(None, normalized, state["last"]).ratio() if normalized and state["last"] else 0
                if normalized and (normalized == state["last"] or similarity >= 0.78):
                    state["repeats"] += 1
                else:
                    state["last"] = normalized
                    state["repeats"] = 0
                if state["repeats"] >= 2:
                    await notify_operators(event, text, "Takroriy support murojaati")
                    await event.reply("Kechirasiz, suhbat tugatildi. Iltimos, aniq maqsadingiz yoki muammoingizni yozib qoldiring.")
                    return
                first_message = "first" not in state
                state["first"] = True
                if first_message and normalized in {"salom", "assalom", "assalomu alaykum", "hello", "hi"}:
                    await event.reply(
                        "Assalomu alaykum! Sizga qanday yordam bera olaman? "
                        "Aniq maqsadingiz va shikoyatingizni yozib qoldiring, muammoni hal qilishga yordam beraman."
                    )
                    return
                if not is_xsnot_related(text) and not state.get("waiting_problem_details"):
                    await notify_operators(event, text, "Botdan tashqari murojaat")
                    await event.reply(
                        "Iltimos, bot bo‘yicha aniq muammoni yozib qoldiring. "
                        "Boshqa savollarga javob berilmaydi va suhbat tugatiladi."
                    )
                    return
                if state.get("waiting_problem_details"):
                    escalate = True
                    state["waiting_problem_details"] = False
                elif is_problem_intent(text):
                    state["waiting_problem_details"] = True
                    if "sekin" in text.lower() or "задерж" in text.lower():
                        reply = (
                            "To‘lov sekin ishlayotganidan uzr. Iltimos, qaysi to‘lov turi ekanini "
                            "va qancha vaqt oldin amalga oshirganingizni yozing. Chek yoki to‘lov "
                            "skrinshotini yuboring — operator tekshiradi va tez orada javob beradi."
                        )
                    else:
                        reply = (
                            "Iltimos, bot yoki to‘lov tizimidagi muammoni batafsil yozib qoldiring. "
                            "Qaysi xizmatdan foydalanganingizni va nima ishlamayotganini yozing. "
                            "Operator tekshiradi va tez orada javob beradi."
                        )
                    await event.reply(reply)
                    return
                else:
                    escalate = needs_operator(text)
                if escalate:
                    await notify_operators(event, text, "Yangi support muammosi")
                response = await ai.responses.create(
                    model=os.getenv("OPENAI_MODEL", "gpt-5"),
                    instructions=support_prompt,
                    input=text,
                )
                reply = response.output_text.strip()
                if first_message:
                    reply = "Assalomu alaykum! Sizga qanday yordam bera olaman? Aniq maqsadingiz va shikoyatingizni yozib qoldiring, muammoni hal qilishga yordam beraman.\n\n" + reply
                if escalate:
                    reply += "\n\nMurojaatingiz operatorga yuborildi. Operator tekshiradi va tez orada javob beradi."
                await event.reply(reply)
                logger.info("Support javobi yuborildi: %s", event.id)
            except Exception:
                logger.exception("Support javobi yuborilmadi")

        logger.info("Support AI yoqildi: shaxsiy chatlar | yo'naltiruvchi username: %s", support_chat)
        support_task = asyncio.create_task(support_client.run_until_disconnected())
    else:
        logger.info("Support AI o'chirilgan: SUPPORT_SESSION_STRING yoki OPENAI_API_KEY yo'q")

    await client.run_until_disconnected()
    if support_task:
        await support_task


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("To'xtatildi")
