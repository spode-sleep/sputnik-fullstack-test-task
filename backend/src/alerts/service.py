from src.core.config import async_session_maker
from src.models import Alert
from src.alerts import repository


async def list_alerts() -> list[Alert]:
    async with async_session_maker() as session:
        return await repository.list_all(session)


async def create_alert(file_id: str, level: str, message: str) -> Alert:
    alert = Alert(file_id=file_id, level=level, message=message)
    async with async_session_maker() as session:
        return await repository.create(session, alert)
