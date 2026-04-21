"""
Celery tasks for async file processing.

Optimisation: scan + metadata extraction are merged into a single
`process_file` task that runs inside **one** database session and
one DB round-trip for the initial fetch. Only the final alert
creation is a separate task (it is cheap and naturally decoupled).

The old three-task chain:
    scan_file_for_threats → extract_file_metadata → send_file_alert

becomes:
    process_file → send_file_alert

Each sync Celery task simply calls asyncio.run() — no shared event
loop, no global mutable state, no race conditions.
"""

import asyncio
from pathlib import Path

from celery import Celery

from src.core.config import REDIS_URL, STORAGE_DIR, async_session_maker
from src.models import Alert, StoredFile
from src.alerts import repository as alert_repo

celery_app = Celery("file_tasks", broker=REDIS_URL, backend=REDIS_URL)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _scan_reasons(file_item: StoredFile) -> list[str]:
    """Pure function: derive threat-scan reasons from file metadata."""
    reasons: list[str] = []
    extension = Path(file_item.original_name).suffix.lower()

    if extension in {".exe", ".bat", ".cmd", ".sh", ".js"}:
        reasons.append(f"suspicious extension {extension}")

    if file_item.size > 10 * 1024 * 1024:
        reasons.append("file is larger than 10 MB")

    if (
        extension == ".pdf"
        and file_item.mime_type not in {"application/pdf", "application/octet-stream"}
    ):
        reasons.append("pdf extension does not match mime type")

    return reasons


def _extract_metadata(file_item: StoredFile, stored_path: Path) -> dict:
    """Pure function: build metadata dict from an existing file."""
    metadata: dict = {
        "extension": Path(file_item.original_name).suffix.lower(),
        "size_bytes": file_item.size,
        "mime_type": file_item.mime_type,
    }

    if file_item.mime_type.startswith("text/"):
        content = stored_path.read_text(encoding="utf-8", errors="ignore")
        metadata["line_count"] = len(content.splitlines())
        metadata["char_count"] = len(content)
    elif file_item.mime_type == "application/pdf":
        content = stored_path.read_bytes()
        metadata["approx_page_count"] = max(content.count(b"/Type /Page"), 1)

    return metadata


# ---------------------------------------------------------------------------
# Async implementations
# ---------------------------------------------------------------------------

async def _process_file(file_id: str) -> None:
    """
    Single-session pipeline: scan + extract metadata + update DB.

    One session, one initial DB fetch — replaces the old two-task chain
    that opened separate sessions for scan and metadata extraction.
    """
    async with async_session_maker() as session:
        file_item = await session.get(StoredFile, file_id)
        if not file_item:
            return

        file_item.processing_status = "processing"

        stored_path = STORAGE_DIR / file_item.stored_name
        if not stored_path.exists():
            file_item.processing_status = "failed"
            file_item.scan_status = file_item.scan_status or "failed"
            file_item.scan_details = "stored file not found during processing"
            await session.commit()
            send_file_alert.delay(file_id)
            return

        # --- Scan ---
        reasons = _scan_reasons(file_item)
        file_item.scan_status = "suspicious" if reasons else "clean"
        file_item.scan_details = ", ".join(reasons) if reasons else "no threats found"
        file_item.requires_attention = bool(reasons)

        # --- Metadata ---
        file_item.metadata_json = _extract_metadata(file_item, stored_path)
        file_item.processing_status = "processed"

        await session.commit()

    send_file_alert.delay(file_id)


async def _send_file_alert(file_id: str) -> None:
    async with async_session_maker() as session:
        file_item = await session.get(StoredFile, file_id)
        if not file_item:
            return

        if file_item.processing_status == "failed":
            alert = Alert(file_id=file_id, level="critical", message="File processing failed")
        elif file_item.requires_attention:
            alert = Alert(
                file_id=file_id,
                level="warning",
                message=f"File requires attention: {file_item.scan_details}",
            )
        else:
            alert = Alert(file_id=file_id, level="info", message="File processed successfully")

        await alert_repo.create(session, alert)


# ---------------------------------------------------------------------------
# Celery tasks
# ---------------------------------------------------------------------------

@celery_app.task
def process_file(file_id: str) -> None:
    """Entry-point task: scan + extract metadata in one DB session."""
    asyncio.run(_process_file(file_id))


@celery_app.task
def send_file_alert(file_id: str) -> None:
    asyncio.run(_send_file_alert(file_id))
