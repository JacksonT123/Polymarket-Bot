from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from .models import (
    Wallet, Signal, Position, EquitySnapshot,
    TierHistory, WalletPerformance, NotificationLog,
)
from src.core.enums import WalletStatus, PositionStatus


class WalletRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_address(self, address: str) -> Wallet | None:
        result = await self.session.execute(
            select(Wallet).where(Wallet.address == address)
        )
        return result.scalar_one_or_none()

    async def get_by_status(self, status: WalletStatus) -> list[Wallet]:
        result = await self.session.execute(
            select(Wallet).where(Wallet.status == status.value)
        )
        return list(result.scalars().all())

    async def upsert(self, wallet: Wallet) -> Wallet:
        existing = await self.get_by_address(wallet.address)
        if existing:
            for col in Wallet.__table__.columns:
                if col.name not in ("id", "address"):
                    val = getattr(wallet, col.name, None)
                    if val is not None:
                        setattr(existing, col.name, val)
            return existing
        self.session.add(wallet)
        await self.session.flush()
        return wallet

    async def update_status(self, address: str, status: WalletStatus, **kwargs) -> None:
        values = {"status": status.value, **kwargs}
        await self.session.execute(
            update(Wallet).where(Wallet.address == address).values(**values)
        )

    async def count_by_status(self, status: WalletStatus) -> int:
        result = await self.session.execute(
            select(func.count()).where(Wallet.status == status.value)
        )
        return result.scalar_one()


class SignalRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, signal: Signal) -> Signal:
        self.session.add(signal)
        await self.session.flush()
        return signal

    async def get_recent(self, wallet_id: int, limit: int = 50) -> list[Signal]:
        result = await self.session.execute(
            select(Signal)
            .where(Signal.wallet_id == wallet_id)
            .order_by(Signal.lead_timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_all_recent(self, limit: int = 50) -> list[Signal]:
        result = await self.session.execute(
            select(Signal).order_by(Signal.lead_timestamp.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def get_exec_ratio(self, wallet_id: int, days: int = 7) -> float:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        total = await self.session.execute(
            select(func.count()).where(
                Signal.wallet_id == wallet_id,
                Signal.lead_timestamp >= since,
            )
        )
        executed = await self.session.execute(
            select(func.count()).where(
                Signal.wallet_id == wallet_id,
                Signal.lead_timestamp >= since,
                Signal.status == "executed",
            )
        )
        t = total.scalar_one()
        e = executed.scalar_one()
        return e / t if t > 0 else 0.0


class PositionRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, position: Position) -> Position:
        self.session.add(position)
        await self.session.flush()
        return position

    async def get_open(self, is_shadow: bool = False) -> list[Position]:
        result = await self.session.execute(
            select(Position).where(
                Position.status == PositionStatus.OPEN.value,
                Position.is_shadow == is_shadow,
            )
        )
        return list(result.scalars().all())

    async def get_open_for_market(self, market_id: str, side: str, is_shadow: bool = False) -> Position | None:
        result = await self.session.execute(
            select(Position).where(
                Position.market_id == market_id,
                Position.side == side,
                Position.status == PositionStatus.OPEN.value,
                Position.is_shadow == is_shadow,
            )
        )
        return result.scalar_one_or_none()

    async def get_open_for_wallet(self, wallet_id: int, is_shadow: bool = False) -> list[Position]:
        result = await self.session.execute(
            select(Position).where(
                Position.wallet_id == wallet_id,
                Position.status == PositionStatus.OPEN.value,
                Position.is_shadow == is_shadow,
            )
        )
        return list(result.scalars().all())

    async def count_open(self, is_shadow: bool = False) -> int:
        result = await self.session.execute(
            select(func.count()).where(
                Position.status == PositionStatus.OPEN.value,
                Position.is_shadow == is_shadow,
            )
        )
        return result.scalar_one()

    async def sum_deployed(self, is_shadow: bool = False) -> float:
        result = await self.session.execute(
            select(func.sum(Position.cost_usd)).where(
                Position.status == PositionStatus.OPEN.value,
                Position.is_shadow == is_shadow,
            )
        )
        return result.scalar_one() or 0.0

    async def count_opened_today(self, is_shadow: bool = False) -> int:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        result = await self.session.execute(
            select(func.count()).where(
                Position.opened_at >= today_start,
                Position.is_shadow == is_shadow,
            )
        )
        return result.scalar_one()


class EquityRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, snapshot: EquitySnapshot) -> EquitySnapshot:
        self.session.add(snapshot)
        await self.session.flush()
        return snapshot

    async def get_last(self) -> EquitySnapshot | None:
        result = await self.session.execute(
            select(EquitySnapshot).order_by(EquitySnapshot.timestamp.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_range(self, since: datetime) -> list[EquitySnapshot]:
        result = await self.session.execute(
            select(EquitySnapshot)
            .where(EquitySnapshot.timestamp >= since)
            .order_by(EquitySnapshot.timestamp.asc())
        )
        return list(result.scalars().all())

    async def get_rolling_avg_bankroll(self, days: int = 7) -> float:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self.session.execute(
            select(func.avg(EquitySnapshot.total_equity)).where(
                EquitySnapshot.timestamp >= since
            )
        )
        return result.scalar_one() or 0.0


class NotificationRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def was_sent_recently(self, message_hash: str, window_seconds: int) -> bool:
        since = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
        result = await self.session.execute(
            select(func.count()).where(
                NotificationLog.message_hash == message_hash,
                NotificationLog.timestamp >= since,
            )
        )
        return result.scalar_one() > 0

    async def log(self, notification: NotificationLog) -> None:
        self.session.add(notification)
        await self.session.flush()
