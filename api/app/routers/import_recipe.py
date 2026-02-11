"""Recipe import routes."""

import asyncio
import logging
import time
import uuid
import hashlib
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db, AsyncSessionLocal
from app.schemas import ImportRequest, BulkImportRequest, ImportResult
from app.services.recipe_importer import import_recipe_from_url, save_recipe_data
from app.services.ai_extractor import extract_recipe_from_image, enrich_recipe_tags

logger = logging.getLogger("butlergroceries.routers.import_recipe")
router = APIRouter(prefix="/api/recipes", tags=["import"])

# In-memory job tracker for background imports
# {job_id: {"status": "pending|processing|success|failed", "result": {...}, ...}}
_import_jobs: dict[str, dict] = {}


@router.post("/import", response_model=ImportResult)
async def import_from_url(data: ImportRequest, db: AsyncSession = Depends(get_db)):
    """Import a recipe from a URL.

    Tries structured data extraction first (recipe-scrapers),
    falls back to AI extraction via Claude.
    """
    logger.info(f"Import request for URL: {data.url}", extra={
        "extra_data": {"url": data.url, "user_id": data.user_id}
    })

    result = await import_recipe_from_url(db, data.url, data.user_id)
    return ImportResult(**result)


@router.post("/import/photo")
async def import_from_photo(
    file: UploadFile = File(...),
    user_id: int = Form(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Import a recipe from a photo — runs in background.

    Immediately saves the photo and returns a job_id.
    Poll /api/recipes/import/jobs/{job_id} for status.
    """
    # Validate file type
    allowed_types = {
        "image/jpeg": "image/jpeg",
        "image/jpg": "image/jpeg",
        "image/png": "image/png",
        "image/webp": "image/webp",
        "image/gif": "image/gif",
        "image/heic": "image/jpeg",
        "image/heif": "image/jpeg",
    }

    content_type = file.content_type or "image/jpeg"
    media_type = allowed_types.get(content_type)
    if not media_type:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image type: {content_type}. Use JPEG, PNG, or WebP."
        )

    # Read image data
    image_data = await file.read()
    if len(image_data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large. Max 20MB.")

    # Save the photo to disk immediately
    settings = get_settings()
    image_dir = Path(settings.image_dir)
    image_dir.mkdir(parents=True, exist_ok=True)

    file_hash = hashlib.md5(image_data).hexdigest()[:12]
    ext = ".jpg" if "jpeg" in media_type else (".png" if "png" in media_type else ".webp")
    orig_filename = f"photo_import_{file_hash}{ext}"
    orig_path = image_dir / orig_filename
    orig_path.write_bytes(image_data)
    saved_image_path = f"/images/{orig_filename}"

    # Create a job and return immediately
    job_id = uuid.uuid4().hex[:12]
    filename = file.filename or "photo"

    _import_jobs[job_id] = {
        "status": "processing",
        "filename": filename,
        "thumbnail": saved_image_path,
        "created_at": time.time(),
        "result": None,
    }

    logger.info(f"Photo import queued: job={job_id}, file={filename} ({len(image_data)} bytes)")

    # Fire off the background task
    asyncio.create_task(
        _process_photo_import(job_id, image_data, media_type, filename, saved_image_path, user_id)
    )

    return {
        "job_id": job_id,
        "status": "processing",
        "filename": filename,
        "thumbnail": saved_image_path,
    }


async def _process_photo_import(
    job_id: str,
    image_data: bytes,
    media_type: str,
    filename: str,
    saved_image_path: str,
    user_id: int | None,
):
    """Background task: extract recipe from photo and save to DB."""
    start_time = time.time()
    logger.info(f"Processing photo import job={job_id}")

    try:
        # Extract recipe via Claude Vision
        recipe_data = await extract_recipe_from_image(image_data, media_type, filename)
        if not recipe_data:
            _import_jobs[job_id] = {
                **_import_jobs[job_id],
                "status": "failed",
                "result": {
                    "status": "failed",
                    "error": "Could not extract recipe from image. Try a clearer photo.",
                    "duration_ms": int((time.time() - start_time) * 1000),
                },
            }
            return

        # Enrich tags
        if not recipe_data.get("tags"):
            recipe_data["tags"] = await enrich_recipe_tags(recipe_data)

        # Save to database (need our own session since we're outside the request)
        async with AsyncSessionLocal() as db:
            result = await save_recipe_data(
                db,
                recipe_data,
                source_url=f"photo:{filename}",
                extraction_method="photo",
                user_id=user_id,
                start_time=start_time,
                source_image_path=saved_image_path,
            )
            await db.commit()

        _import_jobs[job_id] = {
            **_import_jobs[job_id],
            "status": "success" if result.get("status") == "success" else "failed",
            "result": result,
        }
        logger.info(f"Photo import job={job_id} completed: {result.get('recipe_title', '?')}")

    except Exception as e:
        logger.error(f"Photo import job={job_id} failed: {e}", exc_info=True)
        _import_jobs[job_id] = {
            **_import_jobs[job_id],
            "status": "failed",
            "result": {
                "status": "failed",
                "error": str(e),
                "duration_ms": int((time.time() - start_time) * 1000),
            },
        }


@router.get("/import/jobs/{job_id}")
async def get_import_job(job_id: str):
    """Check the status of a background import job."""
    job = _import_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/import/jobs")
async def list_import_jobs():
    """List all recent import jobs (last hour)."""
    cutoff = time.time() - 3600
    jobs = [
        {"job_id": jid, **job}
        for jid, job in _import_jobs.items()
        if job.get("created_at", 0) > cutoff
    ]
    # Newest first
    jobs.sort(key=lambda j: j.get("created_at", 0), reverse=True)
    return jobs


@router.post("/import/bulk", response_model=list[ImportResult])
async def bulk_import(data: BulkImportRequest, db: AsyncSession = Depends(get_db)):
    """Import multiple recipes from URLs."""
    logger.info(f"Bulk import request: {len(data.urls)} URLs", extra={
        "extra_data": {"url_count": len(data.urls), "user_id": data.user_id}
    })

    results = []
    for url in data.urls:
        url = url.strip()
        if not url:
            continue
        logger.info(f"Bulk importing: {url}")
        result = await import_recipe_from_url(db, url, data.user_id)
        results.append(ImportResult(**result))

    success = sum(1 for r in results if r.status == "success")
    failed = sum(1 for r in results if r.status == "failed")
    logger.info(f"Bulk import complete: {success} succeeded, {failed} failed", extra={
        "extra_data": {"success": success, "failed": failed, "total": len(results)}
    })

    return results
