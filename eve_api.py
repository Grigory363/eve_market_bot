import aiohttp

class EveApiService:
    BASE_URL = "https://esi.evetech.net/latest"

    async def get_item_name(self, session: aiohttp.ClientSession, type_id: int) -> str:
        url = f"{self.BASE_URL}/universe/types/{type_id}/?datasource=tranquility"
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get('name', 'Неизвестно')
        return "Неизвестно"

    async def get_market_orders(self, session: aiohttp.ClientSession, region_id: int, type_id: int):
        url = f"{self.BASE_URL}/markets/{region_id}/orders/?type_id={type_id}&order_type=all&datasource=tranquility"
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.json()
        return []

    async def get_prices(self, session: aiohttp.ClientSession, region_id: int, type_id: int):
        orders = await self.get_market_orders(session, region_id, type_id)
        sell_orders = [order['price'] for order in orders if not order['is_buy_order']]
        buy_orders = [order['price'] for order in orders if order['is_buy_order']]
        return (
            min(sell_orders) if sell_orders else None,
            max(buy_orders) if buy_orders else None
        )