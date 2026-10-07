"""Persistent status for the single local generation worker.

Inputs live only in the worker. Restarted jobs fail explicitly, unless their build
was already committed. No inference is silently repeated after a restart.
"""
import time
from sqlalchemy import Float, String, select, delete
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base, BuildRecord


class GenerationJob(Base):
    __tablename__ = "generation_jobs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    stage: Mapped[str] = mapped_column(String(80), default="queued")
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    updated_at: Mapped[float] = mapped_column(Float, default=time.time)
    error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    error_code: Mapped[int | None] = mapped_column(nullable=True)


class JobRepository:
    def __init__(self, repository):
        self.sessions = repository.sessions

    def recover(self):
        with self.sessions() as db:
            for job in db.scalars(select(GenerationJob).where(GenerationJob.status.in_(["queued", "running"]))):
                if db.get(BuildRecord, job.id):
                    job.status, job.stage = "succeeded", "final"
                else:
                    job.status, job.stage = "failed", "interrupted"
                    job.error = "A API reiniciou durante a geração. Envie a referência novamente."
                    job.error_code = 503
                job.updated_at = time.time()
            db.commit()

    def create(self, job_id):
        with self.sessions() as db:
            # Bound history independently from saved projects. Never evict active work.
            old = list(db.scalars(select(GenerationJob.id).where(
                GenerationJob.status.in_(["succeeded", "failed"])
            ).order_by(GenerationJob.created_at.desc()).offset(199)))
            if old:
                db.execute(delete(GenerationJob).where(GenerationJob.id.in_(old)))
            job = GenerationJob(id=job_id)
            db.add(job)
            db.commit()
            return self.snapshot(job)

    def update(self, job_id, **values):
        with self.sessions() as db:
            job = db.get(GenerationJob, job_id)
            for key, value in values.items():
                setattr(job, key, value)
            job.updated_at = time.time()
            db.commit()

    def get(self, job_id):
        with self.sessions() as db:
            job = db.get(GenerationJob, job_id)
            return self.snapshot(job) if job else None

    @staticmethod
    def snapshot(job):
        end = job.updated_at if job.status in {"succeeded", "failed"} else time.time()
        return {"id": job.id, "status": job.status, "stage": job.stage,
                "elapsedSeconds": max(0, int(end - job.created_at)),
                "buildId": job.id if job.status == "succeeded" else None,
                "error": job.error, "errorCode": job.error_code}
