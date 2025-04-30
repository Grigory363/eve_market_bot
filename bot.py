import asyncio
from aiogram import Bot, Dispatcher, Router, types
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from config import API_TOKEN
from logger import logger
import aiohttp

from static_data import CATEGORIES, REGIONS
from eve_api import EveApiService

router = Router()
eve_api = EveApiService()

class EveBot:
    def __init__(self):
        self.user_data = {}

    def get_user(self, user_id):
        if user_id not in self.user_data:
            self.user_data[user_id] = {
                "category": None,
                "type_id": None,
                "regions": set()
            }
        return self.user_data[user_id]

    def clear_user(self, user_id):
        if user_id in self.user_data:
            self.user_data[user_id]["regions"].clear()

    async def send_region_keyboard(self, callback: CallbackQuery):
        keyboard = [
            [InlineKeyboardButton(
                text=f"{'✅ ' if region in self.get_user(callback.from_user.id)['regions'] else ''}{region}",
                callback_data=f"region_toggle:{region}"
            )]
            for region in REGIONS.keys()
        ]
        keyboard.append([
            InlineKeyboardButton(text="📊 Показать цены", callback_data="show_prices")
        ])
        await callback.message.edit_text(
            "Выберите регионы (можно несколько):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )

    async def send_region_keyboard_new(self, message: types.Message):
        user = self.get_user(message.from_user.id)
        keyboard = [
            [InlineKeyboardButton(
                text=f"{'✅ ' if region in user['regions'] else ''}{region}",
                callback_data=f"region_toggle:{region}"
            )]
            for region in REGIONS.keys()
        ]
        keyboard.append([
            InlineKeyboardButton(text="📊 Показать цены", callback_data="show_prices")
        ])

        await message.answer(
            "Выберите регионы (можно несколько):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )

eve_bot = EveBot()

@router.message(Command(commands=["start"]))
async def start(message: types.Message):
    user = eve_bot.get_user(message.from_user.id)
    user["category"] = None
    user["type_id"] = None
    user["regions"].clear()

    await message.answer(
        "Добро пожаловать! Выберите категорию товара.",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="Минералы")],
                [types.KeyboardButton(text="Оборудование")]
            ],
            resize_keyboard=True
        )
    )

@router.message(lambda message: message.text in CATEGORIES.keys())
async def handle_category_choice(message: types.Message):
    category_name = message.text
    user = eve_bot.get_user(message.from_user.id)
    user["category"] = category_name

    keyboard = [
        [types.KeyboardButton(text=item_name)]
        for item_name in CATEGORIES[category_name].keys()
    ]
    keyboard.append([types.KeyboardButton(text="Отмена")])

    await message.answer(
        f"Выберите товар из категории *{category_name}*:",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=keyboard,
            resize_keyboard=True
        )
    )

@router.message(lambda message: message.text in [item for sub in CATEGORIES.values() for item in sub.keys()])
async def handle_item_choice(message: types.Message):
    item_name = message.text
    category_name = eve_bot.get_user(message.from_user.id)["category"]

    if not category_name or item_name not in CATEGORIES.get(category_name, {}):
        await message.answer("❌ Товар не найден.")
        return

    type_id = CATEGORIES[category_name][item_name]
    user = eve_bot.get_user(message.from_user.id)
    user["type_id"] = type_id

    await eve_bot.send_region_keyboard_new(message)

@router.callback_query(lambda c: c.data.startswith("region_toggle:"))
async def toggle_region(callback: CallbackQuery):
    region_name = callback.data.split("region_toggle:")[1]
    user = eve_bot.get_user(callback.from_user.id)

    if region_name in REGIONS:
        if region_name in user["regions"]:
            user["regions"].remove(region_name)
        else:
            user["regions"].add(region_name)

    await eve_bot.send_region_keyboard(callback)

@router.callback_query(lambda c: c.data == "show_prices")
async def show_prices(callback: CallbackQuery):
    user = eve_bot.get_user(callback.from_user.id)
    type_id = user["type_id"]
    regions = user["regions"]

    if not type_id or not regions:
        await callback.message.edit_text("❌ Не выбран товар или регион.")
        return

    async with aiohttp.ClientSession() as session:
        item_name = await eve_api.get_item_name(session, type_id)
        text = f"📦 *{item_name}*:\n"

        for region in regions:
            region_id = REGIONS[region]
            sell_price, buy_price = await eve_api.get_prices(session, region_id, type_id)
            text += (
                f"\n📍 *{region}*\n"
                f"🛒 Продажа: `{sell_price if sell_price else 'нет'}` ISK\n"
                f"💰 Покупка: `{buy_price if buy_price else 'нет'}` ISK\n"
            )

    await callback.message.edit_text(text, parse_mode="Markdown")
    eve_bot.clear_user(callback.from_user.id)

async def main():
    bot = Bot(token=API_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    try:
        logger.info("Starting bot...")
        await dp.start_polling(bot)
    except TelegramAPIError as e:
        logger.exception(f"Telegram API error: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
    finally:
        logger.info("Bot stopped.")

if __name__ == "__main__":
    asyncio.run(main())
