from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
import aiohttp
from logger import logger  # <-- добавляем импорт логгера

from config import REGIONS, CATEGORIES
from eve_api import EveApiService

class MarketBot:
    def __init__(self):
        self.router = Router()
        self.eve_api = EveApiService()
        self.user_selected_category = {}
        self.user_selected_item = {}
        self._register_handlers()

    def _register_handlers(self):
        self.router.message(Command("start"))(self.start_command)
        self.router.message(Command("item"))(self.choose_category)
        self.router.callback_query(F.data.startswith("category:"))(self.handle_category_choice)
        self.router.callback_query(F.data.startswith("item:"))(self.handle_item_choice)
        self.router.callback_query(F.data.startswith("region:"))(self.handle_region_choice)

    async def start_command(self, message: types.Message):
        logger.info(f"User {message.from_user.id} started bot")
        await message.answer("Привет! 👋\nНажмите /item для просмотра товаров.")

    async def choose_category(self, message: types.Message):
        logger.info(f"User {message.from_user.id} is choosing a category")
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=category, callback_data=f"category:{category}")]
                for category in CATEGORIES.keys()
            ]
        )
        await message.answer("Выберите категорию товаров:", reply_markup=keyboard)

    async def handle_category_choice(self, callback: CallbackQuery):
        category_name = callback.data.split("category:")[1]
        logger.info(f"User {callback.from_user.id} selected category: {category_name}")

        if category_name not in CATEGORIES:
            await callback.message.edit_text("❌ Категория не найдена.")
            return

        self.user_selected_category[callback.from_user.id] = category_name

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=item, callback_data=f"item:{item}")]
                for item in CATEGORIES[category_name].keys()
            ]
        )
        await callback.message.edit_text(
            f"📚 Вы выбрали категорию *{category_name}*.\nТеперь выберите товар:",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

    async def handle_item_choice(self, callback: CallbackQuery):
        item_name = callback.data.split("item:")[1]
        logger.info(f"User {callback.from_user.id} selected item: {item_name}")

        category_name = self.user_selected_category.get(callback.from_user.id)

        if not category_name or item_name not in CATEGORIES.get(category_name, {}):
            await callback.message.edit_text("❌ Товар не найден.")
            return

        type_id = CATEGORIES[category_name][item_name]
        self.user_selected_item[callback.from_user.id] = type_id

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=region, callback_data=f"region:{region}")]
                for region in REGIONS.keys()
            ]
        )
        await callback.message.edit_text(
            f"🧱 Вы выбрали товар *{item_name}*.\nТеперь выберите регион:",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

    async def handle_region_choice(self, callback: CallbackQuery):
        region_name = callback.data.split("region:")[1]
        logger.info(f"User {callback.from_user.id} selected region: {region_name}")

        region_id = REGIONS.get(region_name)
        type_id = self.user_selected_item.get(callback.from_user.id)

        if not type_id or not region_id:
            await callback.message.edit_text("❌ Что-то пошло не так. Попробуйте снова.")
            return

        async with aiohttp.ClientSession() as session:
            item_name = await self.eve_api.get_item_name(session, type_id)
            sell_price, buy_price = await self.eve_api.get_prices(session, region_id, type_id)

        if sell_price is None and buy_price is None:
            text = f"🔍 В регионе {region_name} нет данных по '{item_name}'"
        else:
            text = (
                f"📦 *{item_name}* в регионе *{region_name}*:\n"
                f"🛒 Продажа: `{sell_price if sell_price else 'нет'}` ISK\n"
                f"💰 Покупка: `{buy_price if buy_price else 'нет'}` ISK"
            )
        await callback.message.edit_text(text, parse_mode="Markdown")