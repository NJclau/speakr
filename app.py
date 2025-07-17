from fastapi import FastAPI, APIRouter, Depends, HTTPException, BackgroundTasks, File, UploadFile, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from models import Job, TranscriptSegment, User, Organization  # SQLAlchemy models
from database import get_db  # async session dependency
from auth import auth_service, UserRole  # authentication service
from processing import audio_processor, job_queue, JobPriority, AsyncJobQueue  # processing classes

router = APIRouter(prefix="/api", tags=["jobs"])

# Pydantic schemas
class JobCreateRequest(BaseModel):
    language: str = "auto"
    target_language: Optional[str] = None
    enable_diarization: bool = True
    model_size: str = "medium"
    priority: JobPriority = JobPriority.NORMAL
    processing_options: Dict[str, Any] = {}
    custom_vocabulary: Optional[List[str]] = None

class JobResponse(BaseModel):
    id: uuid.UUID
    status: str
    queue_position: Optional[int]
    estimated_wait_time: Optional[str]
    created_at: datetime
    progress: Optional[int]
    error_message: Optional[str]

class TranscriptSegmentOut(BaseModel):
    start: float
    end: float
    text: str
    confidence: float
    speaker: Optional[str]
    language: Optional[str]

class TranscriptResponse(BaseModel):
    id: uuid.UUID
    segments: List[TranscriptSegmentOut]
    metadata: Dict[str, Any]
    summary: Optional[str]
    export_formats: List[str] = ["txt", "srt", "vtt", "json", "docx"]

# Endpoint: Upload and create job
@router.post("/upload", response_model=JobResponse)
async def create_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    payload: JobCreateRequest = Depends(),
    current_user = Depends(auth_service.check_permissions(UserRole.USER)),
    db: AsyncSession = Depends(get_db)
):
    # 1. Persist file to storage
    job_id = uuid.uuid4()
    file_location = f"/data/uploads/{job_id}_{file.filename}"
    with open(file_location, "wb") as f:
        content = await file.read()
        f.write(content)

    # 2. Create DB job record
    new_job = Job(
        id=job_id,
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        status="pending",
        original_filename=file.filename,
        file_size=len(content),
        language=payload.language,
        target_language=payload.target_language,
        processing_options=payload.processing_options,
        created_at=datetime.utcnow(),
    )
    db.add(new_job)
    await db.commit()
    await db.refresh(new_job)

    # 3. Queue the job
    queue_job = AsyncJobQueue.redis_job_from_db(new_job)
    position = await job_queue.add_job(queue_job)

    # 4. Launch background processing
    background_tasks.add_task(process_and_finalize, queue_job, db)

    return JobResponse(
        id=new_job.id,
        status=new_job.status,
        queue_position=position,
        estimated_wait_time=None,
        created_at=new_job.created_at,
        progress=0,
        error_message=None
    )

async def process_and_finalize(queue_job, db: AsyncSession):
    try:
        # process audio and get segments + metadata
        segments, metadata = await audio_processor.process_audio(
            audio_file_path=queue_job.audio_url,
            language=queue_job.processing_options.get("language", "auto"),
            enable_diarization=queue_job.priority,
            model_size=queue_job.processing_options.get("model_size", "medium"),
            processing_options=queue_job.processing_options
        )
        # save transcript
        job = await db.get(Job, queue_job.id)
        job.transcript_data = [seg.__dict__ for seg in segments]
        job.job_metadata = metadata
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        await db.commit()
    except Exception as e:
        job = await db.get(Job, queue_job.id)
        job.status = "failed"
        job.error_message = str(e)
        job.completed_at = datetime.utcnow()
        await db.commit()

# Endpoint: Get job status
@router.get("/status/{job_id}")
async def get_status(
    job_id: uuid.UUID,
    current_user = Depends(auth_service.authenticate_user),
    db: AsyncSession = Depends(get_db)
):
    job = await db.get(Job, job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")
    # Build response
    return JobResponse(
        id=job.id,
        status=job.status,
        queue_position=job.queue_position,
        estimated_wait_time=None,
        created_at=job.created_at,
        progress=0,
        error_message=job.error_message
    )

# Endpoint: Retrieve transcript
@router.get("/transcript/{job_id}", response_model=TranscriptResponse)
async def get_transcript(
    job_id: uuid.UUID,
    export: Optional[str] = Query(None, description="Format to export"),
    current_user = Depends(auth_service.authenticate_user),
    db: AsyncSession = Depends(get_db)
):
    job = await db.get(Job, job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found or access denied")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Transcript not ready")

    segments = [TranscriptSegmentOut(**seg) for seg in job.transcript_data]
    resp = TranscriptResponse(
        id=job.id,
        segments=segments,
        metadata=job.job_metadata,
        summary=job.job_metadata.get("summary"),
    )
    # TODO: handle export format streaming
    return resp

# Endpoint: Delete transcript
@router.delete("/transcript/{job_id}")
async def delete_transcript(
    job_id: uuid.UUID,
    current_user = Depends(auth_service.check_permissions(UserRole.USER)),
    db: AsyncSession = Depends(get_db)
):
    job = await db.get(Job, job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")
    await db.delete(job)
    await db.commit()
    return JSONResponse({"deleted": True, "retentionEnd": (datetime.utcnow() + timedelta(days=30)).isoformat()})

# Mount router
app = FastAPI()
app.include_router(router)
