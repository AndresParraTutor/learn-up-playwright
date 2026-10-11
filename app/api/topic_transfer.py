from __future__ import annotations

import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path

from app.services.topic_transfer import (
    MAX_ARCHIVE_BYTES,
    TopicTransferError,
    TransferRoots,
    export_topic,
    import_topic,
)
from app.services.topic_transfer_adapter import get_adapter
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

router = APIRouter(tags=["topic-transfer"])
REPO_ROOT = Path(__file__).resolve().parents[2]
TRUST_WARNING = (
    "Import learn-up topics only from people and sources you trust. "
    "Validation reduces common archive risks, but it cannot make an untrusted archive safe."
)


@router.get("/api/t/{topic_slug}/export")
def download_topic(topic_slug: str) -> FileResponse:
    temporary = Path(tempfile.mkdtemp(prefix="learnup-topic-export-"))
    output = temporary / f"{topic_slug}.learnup.zip"
    try:
        export_topic(
            TransferRoots.from_repo(REPO_ROOT), get_adapter(), topic_slug, output
        )
    except TopicTransferError as exc:
        shutil.rmtree(temporary, ignore_errors=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return FileResponse(
        output,
        media_type="application/zip",
        filename=output.name,
        background=BackgroundTask(shutil.rmtree, temporary, True),
    )


@router.post("/api/topics/import")
async def upload_topic(
    request: Request, dry_run: bool = True, confirm: bool = False
) -> dict[str, object]:
    if dry_run == confirm:
        raise HTTPException(
            status_code=400, detail="Choose exactly one of dry_run=true or confirm=true"
        )
    content_type = (
        request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    )
    if content_type not in {"application/zip", "application/octet-stream"}:
        raise HTTPException(
            status_code=415, detail="Request body must be a ZIP archive"
        )
    temporary = Path(tempfile.mkdtemp(prefix="learnup-topic-upload-"))
    archive = temporary / "upload.learnup.zip"
    size = 0
    try:
        with archive.open("xb") as stream:
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_ARCHIVE_BYTES:
                    raise HTTPException(
                        status_code=413, detail="Archive exceeds upload limit"
                    )
                stream.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="Archive body is empty")
        report = await run_in_threadpool(
            import_topic,
            archive,
            TransferRoots.from_repo(REPO_ROOT),
            get_adapter(),
            confirm=confirm,
        )
        result = asdict(report)
        result["trust_warning"] = TRUST_WARNING
        return result
    except TopicTransferError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
