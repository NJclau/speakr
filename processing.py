import os
import asyncio
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import redis.asyncio as redis
import whisper
import tempfile
import subprocess
from pathlib import Path

class JobStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class JobPriority(int, Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4

@dataclass
class QueueJob:
    id: str
    user_id: str
    organization_id: Optional[str]
    priority: JobPriority
    audio_url: str
    processing_options: Dict
    created_at: datetime
    estimated_duration: Optional[int] = None

class AsyncJobQueue:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.processing_jobs: Dict[str, QueueJob] = {}
        self.max_concurrent_jobs = 10

    async def add_job(self, job: QueueJob) -> int:
        """Add job to priority queue and return queue position"""
        # Serialize job data
        job_data = {
            "id": job.id,
            "user_id": job.user_id,
            "organization_id": job.organization_id,
            "priority": job.priority.value,
            "audio_url": job.audio_url,
            "processing_options": job.processing_options,
            "created_at": job.created_at.isoformat(),
            "estimated_duration": job.estimated_duration
        }

        # Add to priority queue (higher priority = lower score)
        queue_key = f"job_queue:{job.priority.value}"
        await self.redis.zadd(queue_key, {json.dumps(job_data): datetime.timestamp(datetime.now())})

        # Update job status in database
        await self.update_job_status(job.id, JobStatus.QUEUED)

        # Return queue position
        return await self.get_queue_position(job.id)

    async def get_next_job(self) -> Optional[QueueJob]:
        """Get next job from priority queue"""
        if len(self.processing_jobs) >= self.max_concurrent_jobs:
            return None

        # Check queues by priority (highest first)
        for priority in [JobPriority.URGENT, JobPriority.HIGH, JobPriority.NORMAL, JobPriority.LOW]:
            queue_key = f"job_queue:{priority.value}"
            result = await self.redis.zpopmin(queue_key)

            if result:
                job_data = json.loads(result[0][0])
                job = QueueJob(
                    id=job_data["id"],
                    user_id=job_data["user_id"],
                    organization_id=job_data["organization_id"],
                    priority=JobPriority(job_data["priority"]),
                    audio_url=job_data["audio_url"],
                    processing_options=job_data["processing_options"],
                    created_at=datetime.fromisoformat(job_data["created_at"]),
                    estimated_duration=job_data.get("estimated_duration")
                )

                self.processing_jobs[job.id] = job
                await self.update_job_status(job.id, JobStatus.PROCESSING)
                return job

        return None

    async def complete_job(self, job_id: str, success: bool = True):
        """Mark job as completed and remove from processing"""
        if job_id in self.processing_jobs:
            del self.processing_jobs[job_id]

        status = JobStatus.COMPLETED if success else JobStatus.FAILED
        await self.update_job_status(job_id, status)

    async def get_queue_position(self, job_id: str) -> int:
        """Get current queue position for a job"""
        position = 0

        # Check all priority queues
        for priority in [JobPriority.URGENT, JobPriority.HIGH, JobPriority.NORMAL, JobPriority.LOW]:
            queue_key = f"job_queue:{priority.value}"
            jobs = await self.redis.zrange(queue_key, 0, -1)

            for i, job_data in enumerate(jobs):
                job_info = json.loads(job_data)
                if job_info["id"] == job_id:
                    return position + i + 1

            position += len(jobs)

        return 0  # Not found in queue

    async def update_job_status(self, job_id: str, status: JobStatus):
        """Update job status in database"""
        from database import get_db
        from models import Job
        async with get_db() as db:
            job = await db.get(Job, job_id)
            if job:
                job.status = status.value
                if status == JobStatus.PROCESSING:
                    job.started_at = datetime.utcnow()
                elif status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                    job.completed_at = datetime.utcnow()
                    if job.started_at:
                        job.processing_time_ms = int((job.completed_at - job.started_at).total_seconds() * 1000)

                await db.commit()

# Initialize queue
redis_client = redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
job_queue = AsyncJobQueue(redis_client)

@dataclass
class TranscriptionSegment:
    start: float
    end: float
    text: str
    confidence: float
    speaker: Optional[str] = None
    language: Optional[str] = None

class AudioProcessor:
    def __init__(self):
        self.supported_languages = {
            'en': 'English',
            'rw': 'Kinyarwanda',
            'fr': 'French',
            'sw': 'Swahili'
        }
        self.whisper_models = {
            'small': None,
            'medium': None,
            'large': None
        }
        self.load_models()

    def load_models(self):
        """Load Whisper models on startup"""
        for model_size in self.whisper_models.keys():
            try:
                self.whisper_models[model_size] = whisper.load_model(model_size)
            except Exception as e:
                print(f"Failed to load {model_size} model: {e}")

    async def process_audio(
        self,
        audio_file_path: str,
        language: str = "auto",
        enable_diarization: bool = True,
        model_size: str = "medium",
        processing_options: Dict = None
    ) -> Tuple[List[TranscriptionSegment], Dict]:
        """
        Process audio file with transcription and optional speaker diarization
        """
        processing_options = processing_options or {}

        # Step 1: Audio preprocessing
        processed_audio_path = await self._preprocess_audio(audio_file_path)

        # Step 2: Transcription
        segments = await self._transcribe_audio(
            processed_audio_path,
            language,
            model_size,
            processing_options
        )

        # Step 3: Speaker diarization (if enabled)
        if enable_diarization:
            segments = await self._add_speaker_diarization(processed_audio_path, segments)

        # Step 4: Language-specific post-processing
        if language == "rw":
            segments = await self._postprocess_kinyarwanda(segments)

        # Step 5: Generate metadata
        metadata = await self._generate_metadata(segments, processing_options)

        # Cleanup temporary files
        await self._cleanup_temp_files([processed_audio_path])

        return segments, metadata

    async def _preprocess_audio(self, audio_path: str) -> str:
        """Preprocess audio for better transcription quality"""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            output_path = temp_file.name

        # FFmpeg command for audio preprocessing
        cmd = [
            'ffmpeg', '-i', audio_path,
            '-ar', '16000',  # 16kHz sample rate
            '-ac', '1',      # Mono
            '-c:a', 'pcm_s16le',  # 16-bit PCM
            '-y',            # Overwrite output
            output_path
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise Exception(f"Audio preprocessing failed: {stderr.decode()}")

        return output_path

    async def _transcribe_audio(
        self,
        audio_path: str,
        language: str,
        model_size: str,
        processing_options: Dict
    ) -> List[TranscriptionSegment]:
        """Transcribe audio using Whisper model"""
        model = self.whisper_models.get(model_size)
        if not model:
            raise Exception(f"Model {model_size} not available")

        # Whisper transcription options
        whisper_options = {
            'language': None if language == "auto" else language,
            'task': 'transcribe',
            'temperature': processing_options.get('temperature', 0.0),
            'best_of': processing_options.get('best_of', 1),
            'beam_size': processing_options.get('beam_size', 1),
            'patience': processing_options.get('patience', 1.0),
            'suppress_tokens': processing_options.get('suppress_tokens', "-1"),
            'initial_prompt': processing_options.get('initial_prompt', ""),
            'condition_on_previous_text': processing_options.get('condition_on_previous_text', True),
            'fp16': processing_options.get('fp16', True),
            'compression_ratio_threshold': processing_options.get('compression_ratio_threshold', 2.4),
            'logprob_threshold': processing_options.get('logprob_threshold', -1.0),
            'no_speech_threshold': processing_options.get('no_speech_threshold', 0.6)
        }

        # Run transcription in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: model.transcribe(audio_path, **whisper_options)
        )

        # Convert to TranscriptionSegment objects
        segments = []
        for segment in result['segments']:
            segments.append(TranscriptionSegment(
                start=segment['start'],
                end=segment['end'],
                text=segment['text'].strip(),
                confidence=segment.get('confidence', 0.0),
                language=result.get('language', language)
            ))

        return segments

    async def _add_speaker_diarization(
        self,
        audio_path: str,
        segments: List[TranscriptionSegment]
    ) -> List[TranscriptionSegment]:
        """Add speaker diarization using pyannote.audio"""
        try:
            from pyannote.audio import Pipeline

            # Load speaker diarization pipeline
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=os.environ.get("HUGGINGFACE_TOKEN")
            )

            # Run diarization
            diarization = pipeline(audio_path)

            # Map speakers to segments
            for segment in segments:
                segment_start = segment.start
                segment_end = segment.end
                segment_center = (segment_start + segment_end) / 2

                # Find speaker at segment center
                for turn, _, speaker in diarization.itertracks(yield_label=True):
                    if turn.start <= segment_center <= turn.end:
                        segment.speaker = speaker
                        break

                # Default to SPEAKER_00 if no speaker found
                if not segment.speaker:
                    segment.speaker = "SPEAKER_00"

            return segments

        except Exception as e:
            print(f"Speaker diarization failed: {e}")
            # Return segments without speaker info
            return segments

    async def _postprocess_kinyarwanda(
        self,
        segments: List[TranscriptionSegment]
    ) -> List[TranscriptionSegment]:
        """Post-process Kinyarwanda transcription for better accuracy"""
        # Common Kinyarwanda corrections
        corrections = {
            'mu': 'mu',
            'ku': 'ku',
            'kw': 'kw',
            'gw': 'gw',
            'by': 'by',
            'py': 'py',
            'my': 'my',
            'ny': 'ny',
            'ry': 'ry',
            'cy': 'cy',
            'dy': 'dy',
            'ty': 'ty',
            'fy': 'fy',
            'hy': 'hy',
            'jy': 'jy',
            'ky': 'ky',
            'ly': 'ly',
            'sy': 'sy',
            'vy': 'vy',
            'wy': 'wy',
            'zy': 'zy'
        }

        for segment in segments:
            text = segment.text

            # Apply corrections
            for wrong, correct in corrections.items():
                text = text.replace(wrong, correct)

            # Remove extra spaces
            text = ' '.join(text.split())

            segment.text = text

        return segments

    async def _generate_metadata(
        self,
        segments: List[TranscriptionSegment],
        processing_options: Dict
    ) -> Dict:
        """Generate metadata about the transcription"""
        if not segments:
            return {}

        total_duration = segments[-1].end if segments else 0
        word_count = sum(len(segment.text.split()) for segment in segments)
        avg_confidence = sum(segment.confidence for segment in segments) / len(segments)

        # Speaker statistics
        speakers = set(segment.speaker for segment in segments if segment.speaker)
        speaker_stats = {}
        for speaker in speakers:
            speaker_segments = [s for s in segments if s.speaker == speaker]
            speaker_duration = sum(s.end - s.start for s in speaker_segments)
            speaker_stats[speaker] = {
                'duration': speaker_duration,
                'percentage': (speaker_duration / total_duration) * 100 if total_duration > 0 else 0,
                'segments': len(speaker_segments)
            }

        return {
            'total_duration': total_duration,
            'word_count': word_count,
            'average_confidence': avg_confidence,
            'speaker_count': len(speakers),
            'speaker_stats': speaker_stats,
            'processing_options': processing_options,
            'language_detected': segments[0].language if segments else None
        }

    async def _cleanup_temp_files(self, file_paths: List[str]):
        """Clean up temporary files"""
        for path in file_paths:
            try:
                Path(path).unlink()
            except Exception as e:
                print(f"Failed to cleanup {path}: {e}")

# Initialize processor
audio_processor = AudioProcessor()
import os
