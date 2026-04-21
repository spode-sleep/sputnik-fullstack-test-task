from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Alert


async def list_all(session: AsyncSession) -> list[Alert]:
    result = await session.execute(
        select(Alert).order_by(Alert.created_at.desc())
    )
    return list(result.scalars().all())


async def create(session: AsyncSession, alert: Alert) -> Alert:
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    return alert
