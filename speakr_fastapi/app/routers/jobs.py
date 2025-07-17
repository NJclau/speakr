from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, File, UploadFile, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from datetime import datetime

from .. import models, schemas
from ..database import get_db
from ..auth import auth_service, UserRole

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])

@router.post("/upload", response_model=schemas.JobResponse)
async def create_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    payload: schemas.JobCreateRequest = Depends(),
    current_user: models.User = Depends(auth_service.check_permissions(UserRole.USER)),
    db: AsyncSession = Depends(get_db)
):
    # 1. Persist file to storage
    job_id = uuid.uuid4()
    file_location = f"/data/uploads/{job_id}_{file.filename}"
    with open(file_location, "wb") as f:
        content = await file.read()
        f.write(content)

    # 2. Create DB job record
    new_job = models.Job(
        id=job_id,
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        status="pending",
        original_filename=file.filename,
        file_size=len(content),
        language=payload.language,
        processing_options=payload.processing_options,
        created_at=datetime.utcnow(),
    )
    db.add(new_job)
    await db.commit()
    await db.refresh(new_job)

    # 3. Queue the job (placeholder)
    position = 1 # Placeholder

    # 4. Launch background processing (placeholder)
    # background_tasks.add_task(process_and_finalize, new_job, db)

    return schemas.JobResponse(
        id=new_job.id,
        status=new_job.status,
        queue_position=position,
        estimated_wait_time=None,
        created_at=new_job.created_at,
        progress=0,
        error_message=None
    )

@router.get("/{job_id}", response_model=schemas.JobResponse)
async def get_job(
    job_id: uuid.UUID,
    current_user: models.User = Depends(auth_service.authenticate_user),
    db: AsyncSession = Depends(get_db)
):
    job = await db.get(models.Job, job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")

    return schemas.JobResponse(
        id=job.id,
        status=job.status,
        queue_position=job.queue_position,
        estimated_wait_time=None,
        created_at=job.created_at,
        progress=0,
        error_message=job.error_message
    )

@router.get("/{job_id}/transcript", response_model=schemas.TranscriptResponse)
async def get_transcript(
    job_id: uuid.UUID,
    current_user: models.User = Depends(auth_service.authenticate_user),
    db: AsyncSession = Depends(get_db)
):
    job = await db.get(models.Job, job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found or access denied")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Transcript not ready")

    segments = [schemas.TranscriptSegmentOut(**seg) for seg in job.transcript_data]
    resp = schemas.TranscriptResponse(
        id=job.id,
        segments=segments,
        metadata=job.metadata,
        summary=job.metadata.get("summary"),
    )

    return resp

@router.delete("/{job_id}")
async def delete_job(
    job_id: uuid.UUID,
    current_user: models.User = Depends(auth_service.check_permissions(UserRole.USER)),
    db: AsyncSession = Depends(get_db)
):
    job = await db.get(models.Job, job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")
    await db.delete(job)
    await db.commit()
    return JSONResponse({"deleted": True})
