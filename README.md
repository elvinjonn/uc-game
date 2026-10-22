# OXUNOV FILM bot (@oxunovfilmbot)

Telegram kino boti. Kanal: https://t.me/oxunovfilm · Admin: @oxunov44

## Imkoniyatlar
- **Kino kodi** yozilsa, bot kinoni beradi; kino tagida **💾 Saqlash** tugmasi, izohda «@oxunovfilmbot orqali yuborildi»
- **💾 Saqlanganlar** — saqlangan kinolar ro'yxati + kod yozib yangi kino olish
- **⭐ Top Kinolar** — ko'rishlar bo'yicha, xabar o'zi jonli yangilanadi (10 soniyada, 5 daqiqagacha)
- **🎬 Kinolar qidirish**, **📋 Barcha kinolar** (sahifalab)
- **📸 Instagram** — «Hozircha mavjud emas!»
- **📢 Kanalimiz**, **✍️ Adminga murojaat**

## Ishga tushirish
```bash
pip install -r requirements.txt
export BOT_TOKEN=...        # BotFather tokeni
export ADMIN_IDS=123456789  # admin Telegram ID
python bot.py
```

## Admin: kino qo'shish
Botga (admin akkauntdan) kinoni **yuboring yoki kanaldan forward qiling** — avtomatik bazaga saqlanadi.
- Nom shart emas: kod avtomatik beriladi (1, 2, 3...)
- Izoh yozsangiz, o'sha kinoning nomi bo'ladi; yozmasangiz «Kino 5» kabi
- Bir xil kino ikki marta qo'shilmaydi
- `/del 101` — kinoni o'chirish
- `/list` — kodlar va nomlar ro'yxati
- `/stat` — statistika

## Deploy
Token'ni kodga yozmang — hosting (Railway, Render, VPS) muhit o'zgaruvchilariga `BOT_TOKEN` va `ADMIN_IDS` qo'ying.
Ma'lumotlar `films.db` (SQLite) da saqlanadi; hostingda doimiy disk ulang, aks holda qayta ishga tushganda yo'qoladi.
