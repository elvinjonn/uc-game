import logging
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# Bot tokeni va sozlamalar
BOT_TOKEN = "8724434495:AAHjfSTMwA21-AZPb70ktCscR1HOICo14xA"
CHANNEL_USERNAME = "@elvinorg"
ADMIN_USERNAME = "@oxunov44"
WEB_APP_URL = "https://elvinjonn.github.io/uc-game/"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ["creator", "administrator", "member"]
    except Exception as e:
        print(f"Obuna tekshirishda xatolik: {e}")
        return False

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    is_subscribed = await check_subscription(user_id)

    if not is_subscribed:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📢 Kanalga a'zo bo'lish", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
                [InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_sub")]
            ]
        )
        await message.answer(
            f"👋 Salom, <b>{message.from_user.first_name}</b>!\n\n"
            f"O'yinga kirish uchun rasmiy kanalimizga obuna bo'ling: {CHANNEL_USERNAME}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        await open_game_menu(message)

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: types.CallbackQuery):
    is_subscribed = await check_subscription(callback.from_user.id)
    if is_subscribed:
        await callback.message.delete()
        await callback.message.answer("✅ Obuna tasdiqlandi!")
        await open_game_menu(callback.message)
    else:
        await callback.answer("❌ Siz hali kanalga obuna bo'lmadingiz!", show_alert=True)

async def open_game_menu(message: types.Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎮 O'YINNI BOSHLASH 🚀", web_app=WebAppInfo(url=WEB_APP_URL))],
            [InlineKeyboardButton(text="👨‍💻 Admin bilan aloqa", url=f"https://t.me/{ADMIN_USERNAME.replace('@', '')}")]
