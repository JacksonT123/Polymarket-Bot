"""30-second price update loop for all open positions."""
import asyncio
import structlog
from config.settings import POSITION_PRICE_UPDATE_S
from src.data.polymarket_client import get_client

log = structlog.get_logger(__name__)


class PositionPricer:
    def __init__(self):
        self._client = get_client()
        self._running = False

    async def run(self, get_open_positions, update_position_price) -> None:
        self._running = True
        log.info("pricer_started", interval_s=POSITION_PRICE_UPDATE_S)
        while self._running:
            try:
                await self._update_all(get_open_positions(), update_position_price)
            except Exception as e:
                log.error("pricer_error", error=str(e))
            await asyncio.sleep(POSITION_PRICE_UPDATE_S)

    async def _update_all(self, open_positions: list, update_fn) -> None:
        tasks = [self._update_one(pos, update_fn) for pos in open_positions]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _update_one(self, position, update_fn) -> None:
        try:
            price = await self._client.get_midpoint_price(position.token_id)
            if price is not None:
                unrealized = (price - position.entry_price) * position.size_shares
                await update_fn(position.id, price, unrealized)
        except Exception as e:
            log.debug("price_update_failed", position_id=position.id, error=str(e))

    def stop(self) -> None:
        self._running = False
