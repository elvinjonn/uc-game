import asyncio
import logging
import os

import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

def _load_env(path=".env"):
    """Oddiy .env o'quvchi (qo'shimcha kutubxonasiz)."""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
    except FileNotFoundError:
        pass


_load_env()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x}
DB_PATH = os.getenv("DB_PATH", "films.db")

BOT_USERNAME = "@oxunovfilmbot"
CHANNEL_URL = "https://t.me/oxunovfilm"
ADMIN_URL = "https://t.me/oxunov44"
SIGNATURE = f"📤 {BOT_USERNAME} orqali yuborildi"

LIVE_INTERVAL = 10  # soniya
LIVE_ROUNDS = 30  # 10 soniya x 30 = 5 daqiqa jonli yangilanish
PAGE_SIZE = 10
LIST_PAGE = 30  # Barcha kinolar: bir sahifada nechta

B_SEARCH = "🎬 Kinolar qidirish"
B_ALL = "📋 Barcha kinolar"
B_CHANNEL = "📢 Kanalimiz"
B_INSTA = "📸 Instagram"
B_TOP = "⭐ Top Kinolar"
B_SAVED = "💾 Saqlanganlar"
B_ADMIN = "✍️ Adminga murojaat"

MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=B_SEARCH), KeyboardButton(text=B_ALL)],
        [KeyboardButton(text=B_CHANNEL), KeyboardButton(text=B_INSTA)],
        [KeyboardButton(text=B_TOP), KeyboardButton(text=B_SAVED)],
        [KeyboardButton(text=B_ADMIN)],
    ],
    resize_keyboard=True,
)

dp = Dispatcher(storage=MemoryStorage())


class St(StatesGroup):
    search = State()
    code = State()


# ---------------------------------------------------------------- DB
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS movies(
                code TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                file_id TEXT NOT NULL,
                file_type TEXT NOT NULL DEFAULT 'video',
                views INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS saved(
                user_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                PRIMARY KEY(user_id, code)
            );
            CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY);
            """
        )
        try:
            await db.execute("ALTER TABLE movies ADD COLUMN file_unique_id TEXT")
        except aiosqlite.OperationalError:
            pass  # ustun allaqachon bor
        await db.commit()


async def q_all(sql, args=()):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(sql, args)
        return await cur.fetchall()


async def q_one(sql, args=()):
    rows = await q_all(sql, args)
    return rows[0] if rows else None


async def q_exec(sql, args=()):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(sql, args)
        await db.commit()


# ---------------------------------------------------------------- helpers
def movie_kb(code: str, saved: bool) -> InlineKeyboardMarkup:
    text = "✅ Saqlandi (olib tashlash)" if saved else "💾 Saqlash"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=f"save:{code}")]]
    )


def caption(m) -> str:
    return f"🎬 {m['title']}\n🔑 Kod: {m['code']}\n\n{SIGNATURE}"


async def is_saved(user_id: int, code: str) -> bool:
    return bool(await q_one("SELECT 1 FROM saved WHERE user_id=? AND code=?", (user_id, code)))


async def send_movie(message: Message, user_id: int, code: str) -> bool:
    m = await q_one("SELECT * FROM movies WHERE code=?", (code,))
    if not m:
        return False
    await q_exec("UPDATE movies SET views=views+1 WHERE code=?", (code,))
    kb = movie_kb(code, await is_saved(user_id, code))
    if m["file_type"] == "document":
        await message.answer_document(m["file_id"], caption=caption(m), reply_markup=kb)
    else:
        await message.answer_video(m["file_id"], caption=caption(m), reply_markup=kb)
    return True


def list_kb(rows, prefix_nav: str | None = None, page: int = 0, total: int = 0):
    buttons = [
        [InlineKeyboardButton(text=f"🎬 {r['title']} • {r['code']}", callback_data=f"m:{r['code']}")]
        for r in rows
    ]
    if prefix_nav:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"{prefix_nav}:{page - 1}"))
        if (page + 1) * PAGE_SIZE < total:
            nav.append(InlineKeyboardButton(text="➡️", callback_data=f"{prefix_nav}:{page + 1}"))
        if nav:
            buttons.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ---------------------------------------------------------------- top (jonli)
async def top_payload():
    rows = await q_all("SELECT * FROM movies ORDER BY views DESC, title LIMIT 10")
    if not rows:
        return "⭐ Hozircha kinolar yo'q.", None
    medals = ["🥇", "🥈", "🥉"]
    lines = ["⭐ <b>Top kinolar</b> (jonli)\n"]
    for i, r in enumerate(rows):
        mark = medals[i] if i < 3 else f"{i + 1}."
        lines.append(f"{mark} {r['title']} — 👁 {r['views']}")
    lines.append("\n🔄 Ro'yxat avtomatik yangilanib turadi")
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"▶️ {r['title']} • {r['code']}", callback_data=f"m:{r['code']}")]
            for r in rows
        ]
    )
    return "\n".join(lines), kb


async def live_top(msg: Message):
    last = None
    for _ in range(LIVE_ROUNDS):
        await asyncio.sleep(LIVE_INTERVAL)
        text, kb = await top_payload()
        if text == last:
            continue
        try:
            await msg.edit_text(text, reply_markup=kb, parse_mode="HTML")
            last = text
        except TelegramBadRequest:
            continue
        except Exception:
            return


# ---------------------------------------------------------------- handlers
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await q_exec("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (message.from_user.id,))
    await message.answer(
        "🎬 <b>OXUNOV FILM</b> botiga xush kelibsiz!\n\n"
        "Kino kodini yozing — bot kinoni yuboradi.\nYoki menyudan tanlang 👇",
        reply_markup=MENU,
        parse_mode="HTML",
    )


@dp.message(F.text == B_SEARCH)
async def search_btn(message: Message, state: FSMContext):
    await state.set_state(St.search)
    await message.answer("🔎 Kino nomini yoki kodini yozing:")


@dp.message(F.text == B_ALL)
async def all_btn(message: Message, state: FSMContext):
    await state.clear()
    await show_all(message, 0)


async def show_all(message: Message, page: int, edit: bool = False):
    total = (await q_one("SELECT COUNT(*) c FROM movies"))["c"]
    if not total:
        await message.answer("Hozircha kinolar yo'q.")
        return
    rows = await q_all(
        "SELECT * FROM movies ORDER BY CAST(code AS INTEGER), code LIMIT ? OFFSET ?",
        (LIST_PAGE, page * LIST_PAGE),
    )
    lines = [f"📋 <b>Barcha kinolar</b> ({total} ta)\n"]
    lines += [f"🔑 <code>{r['code']}</code> — {r['title']}" for r in rows]
    lines.append("\n👆 Kodni yozing, bot kinoni yuboradi")
    text = "\n".join(lines)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"all:{page - 1}"))
    if (page + 1) * LIST_PAGE < total:
        nav.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"all:{page + 1}"))
    kb = InlineKeyboardMarkup(inline_keyboard=[nav]) if nav else None
    if edit:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")


@dp.callback_query(F.data.startswith("all:"))
async def all_page(cb: CallbackQuery):
    await show_all(cb.message, int(cb.data.split(":")[1]), edit=True)
    await cb.answer()


@dp.message(F.text == B_CHANNEL)
async def channel_btn(message: Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="📢 Kanalga o'tish", url=CHANNEL_URL)]]
    )
    await message.answer("📢 Telegram kanalimiz: oxunovfilm", reply_markup=kb)


@dp.message(F.text == B_INSTA)
async def insta_btn(message: Message):
    await message.answer("Hozircha mavjud emas!")


@dp.message(F.text == B_ADMIN)
async def admin_btn(message: Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✍️ @oxunov44 ga yozish", url=ADMIN_URL)]]
    )
    await message.answer("Admin: @oxunov44", reply_markup=kb)


@dp.message(F.text == B_TOP)
async def top_btn(message: Message, state: FSMContext):
    await state.clear()
    text, kb = await top_payload()
    sent = await message.answer(text, reply_markup=kb, parse_mode="HTML")
    asyncio.create_task(live_top(sent))


@dp.message(F.text == B_SAVED)
async def saved_btn(message: Message, state: FSMContext):
    await state.set_state(St.code)
    rows = await q_all(
        "SELECT m.* FROM saved s JOIN movies m ON m.code=s.code WHERE s.user_id=? ORDER BY m.title",
        (message.from_user.id,),
    )
    head = "💾 <b>Saqlanganlar</b>\n\n"
    if rows:
        await message.answer(
            head + "Saqlagan kinolaringiz 👇\n\n🔑 Yangi kino uchun kodni yozing:",
            reply_markup=list_kb(rows),
            parse_mode="HTML",
        )
    else:
        await message.answer(
            head + "Hozircha saqlangan kino yo'q.\n\n🔑 Kino kodini yozing, bot kinoni yuboradi. "
            "Kino tagidagi «Saqlash» tugmasi bilan saqlab qo'ying.",
            parse_mode="HTML",
        )


@dp.callback_query(F.data.startswith("m:"))
async def open_movie(cb: CallbackQuery):
    code = cb.data.split(":", 1)[1]
    if not await send_movie(cb.message, cb.from_user.id, code):
        await cb.answer("Kino topilmadi", show_alert=True)
        return
    await cb.answer()


@dp.callback_query(F.data.startswith("save:"))
async def toggle_save(cb: CallbackQuery):
    code = cb.data.split(":", 1)[1]
    uid = cb.from_user.id
    if await is_saved(uid, code):
        await q_exec("DELETE FROM saved WHERE user_id=? AND code=?", (uid, code))
        saved, note = False, "Saqlanganlardan olib tashlandi"
    else:
        await q_exec("INSERT OR IGNORE INTO saved(user_id, code) VALUES(?,?)", (uid, code))
        saved, note = True, "💾 Saqlandi!"
    try:
        await cb.message.edit_reply_markup(reply_markup=movie_kb(code, saved))
    except TelegramBadRequest:
        pass
    await cb.answer(note)


# ---------------------------------------------------------------- admin
def admin_only(message: Message) -> bool:
    return message.from_user.id in ADMIN_IDS


async def next_code() -> str:
    row = await q_one("SELECT MAX(CAST(code AS INTEGER)) m FROM movies WHERE code GLOB '[0-9]*'")
    return str((row["m"] or 0) + 1)


@dp.message(F.video | F.document, admin_only)
async def admin_add(message: Message):
    """Admin video yuborsa yoki forward qilsa, avtomatik bazaga saqlanadi."""
    media = message.video or message.document
    ftype = "video" if message.video else "document"
    if ftype == "document" and not (media.mime_type or "").startswith("video"):
        return  # video bo'lmagan hujjatlar e'tiborsiz

    fid, uid = media.file_id, media.file_unique_id
    dup = await q_one("SELECT * FROM movies WHERE file_unique_id=?", (uid,))
    if dup:
        await message.answer(f"⚠️ Bu kino bazada bor: {dup['title']} (kod: {dup['code']})")
        return

    # Kod har doim avtomatik beriladi; nom shart emas (izoh bo'lsa, nom bo'ladi)
    code = await next_code()
    cap = (message.caption or "").strip()
    title = cap.splitlines()[0][:100] if cap else f"Kino {code}"

    await q_exec(
        "INSERT INTO movies(code,title,file_id,file_type,file_unique_id) VALUES(?,?,?,?,?) "
        "ON CONFLICT(code) DO UPDATE SET title=excluded.title, file_id=excluded.file_id, "
        "file_type=excluded.file_type, file_unique_id=excluded.file_unique_id",
        (code, title, fid, ftype, uid),
    )
    await message.answer(f"✅ Bazaga saqlandi\n🎬 {title}\n🔑 Kod: {code}")


@dp.message(Command("del"), admin_only)
async def admin_del(message: Message):
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Foydalanish: /del kod")
        return
    await q_exec("DELETE FROM movies WHERE code=?", (parts[1],))
    await q_exec("DELETE FROM saved WHERE code=?", (parts[1],))
    await message.answer("🗑 O'chirildi")


@dp.message(Command("list"), admin_only)
async def admin_list(message: Message):
    await show_all(message, 0)


@dp.message(Command("stat"), admin_only)
async def admin_stat(message: Message):
    u = (await q_one("SELECT COUNT(*) c FROM users"))["c"]
    m = (await q_one("SELECT COUNT(*) c FROM movies"))["c"]
    await message.answer(f"👥 Foydalanuvchilar: {u}\n🎬 Kinolar: {m}")


# ---------------------------------------------------------------- matn: qidiruv / kod
@dp.message(St.search, F.text)
async def do_search(message: Message, state: FSMContext):
    await state.clear()
    text = message.text.strip()
    if await send_movie(message, message.from_user.id, text):
        return
    rows = await q_all(
        "SELECT * FROM movies WHERE title LIKE ? ORDER BY views DESC LIMIT ?",
        (f"%{text}%", PAGE_SIZE),
    )
    if rows:
        await message.answer("🔎 Topilgan kinolar:", reply_markup=list_kb(rows))
    else:
        await message.answer("❌ Hech narsa topilmadi.")


@dp.message(F.text)
async def by_code(message: Message, state: FSMContext):
    text = message.text.strip()
    if await send_movie(message, message.from_user.id, text):
        return
    await message.answer("❌ Bunday kodli kino topilmadi. Kodni tekshirib qayta yozing.")


async def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN o'rnatilmagan")
    logging.basicConfig(level=logging.INFO)
    await init_db()
    bot = Bot(BOT_TOKEN)
    # Bepul hostinglar "port" talab qiladi: kichik veb-server (health check)
    port = os.getenv("PORT")
    if port:
        from aiohttp import web

        app = web.Application()
        app.router.add_get("/", lambda r: web.Response(text="OXUNOV FILM bot ishlayapti"))
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", int(port)).start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
