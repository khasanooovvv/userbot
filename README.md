# Telegram xabar forwarder

Bu Telethon asosidagi userbot. U foydalanuvchi akkauntiga ulanadi va tanlangan manba chatdagi yangi xabarlarni bir yoki bir nechta chatga yuboradi.

## Ishga tushirish

PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env` faylida `API_ID`, `API_HASH`, telefon raqami, manba va manzil chatlarini kiriting. API ma'lumotlarini `my.telegram.org` saytidan oling. So'ng:

```powershell
python main.py
```

Birinchi ishga tushishda Telegram kodi va 2FA paroli so'raladi. Session fayli shu papkada saqlanadi va keyingi safar qayta login talab qilinmaydi.

`MODE=forward` manba ko'rsatkichini saqlaydi. `MODE=copy` esa xabarni manbasiz nusxalaydi.

## Railway uchun session

Lokal login tugagach, session string oling:

```powershell
python export_session.py
```

Chiqqan uzun qiymatni Railway Variables bo'limida `SESSION_STRING` nomi bilan saqlang. Railway'da `SESSION_STRING` bo'lsa, dastur login kodini qayta so'ramaydi.

## Username yo'q bo'lsa

Private kanal yoki guruh uchun ID olish:

```powershell
python list_chats.py
```

Ro'yxatdagi kerakli chatning ID'sini `.env` fayliga yozing. Kanal ID'si odatda `-100` bilan boshlanadi:

```env
DESTINATION_CHATS=-1001234567890
```
