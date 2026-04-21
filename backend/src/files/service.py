import mimetypes
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from src.core.config import STORAGE_DIR, async_session_maker
from src.models import StoredFile
from src.files import repository


async def list_files() -> list[StoredFile]:
    async with async_session_maker() as session:
        return await repository.list_all(session)


async def get_file(file_id: str) -> StoredFile:
    async with async_session_maker() as session:
        file_item = await repository.get_by_id(session, file_id)
        if not file_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        return file_item


async def create_file(title: str, upload_file: UploadFile) -> StoredFile:
    content = await upload_file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty")

    file_id = str(uuid4())
    suffix = Path(upload_file.filename or "").suffix
    stored_name = f"{file_id}{suffix}"
    stored_path = STORAGE_DIR / stored_name
    stored_path.write_bytes(content)

    file_item = StoredFile(
        id=file_id,
        title=title,
        original_name=upload_file.filename or stored_name,
        stored_name=stored_name,
        mime_type=(
            upload_file.content_type
            or mimetypes.guess_type(stored_name)[0]
            or "application/octet-stream"
        ),
        size=len(content),
        processing_status="uploaded",
    )

    async with async_session_maker() as session:
        return await repository.save(session, file_item)


async def update_file(file_id: str, title: str) -> StoredFile:
    async with async_session_maker() as session:
        file_item = await repository.get_by_id(session, file_id)
        if not file_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        file_item.title = title
        return await repository.save(session, file_item)


async def delete_file(file_id: str) -> None:
    async with async_session_maker() as session:
        file_item = await repository.get_by_id(session, file_id)
        if not file_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        stored_path = STORAGE_DIR / file_item.stored_name
        if stored_path.exists():
            stored_path.unlink()
        await repository.delete(session, file_item)


async def get_file_path(file_id: str) -> tuple[StoredFile, Path]:
    file_item = await get_file(file_id)
    stored_path = STORAGE_DIR / file_item.stored_name
    if not stored_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file not found")
    return file_item, stored_path
