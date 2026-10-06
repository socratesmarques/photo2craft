from datetime import datetime, timezone
from sqlalchemy import JSON, DateTime, String, create_engine, event, select, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

class Base(DeclarativeBase): pass

class BuildRecord(Base):
    __tablename__ = "builds"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    structure: Mapped[dict] = mapped_column(JSON)
    options: Mapped[dict] = mapped_column(JSON, default=dict)
    has_image: Mapped[bool] = mapped_column(default=False)

class BuildRepository:
    def __init__(self, url: str):
        sqlite = url.startswith("sqlite")
        self.engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 20} if sqlite else {})
        if sqlite:
            @event.listens_for(self.engine, "connect")
            def configure(dbapi_connection, _):
                dbapi_connection.execute("PRAGMA journal_mode=WAL")
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def initialize(self): Base.metadata.create_all(self.engine)
    def count(self):
        with self.sessions() as db: return db.scalar(select(func.count()).select_from(BuildRecord))
    def save(self, record):
        with self.sessions() as db: db.add(record); db.commit()
        return record
    def get(self, build_id):
        with self.sessions() as db: return db.get(BuildRecord, build_id)
    def list(self, offset, limit):
        with self.sessions() as db:
            return list(db.scalars(select(BuildRecord).order_by(BuildRecord.created_at.desc()).offset(offset).limit(limit)))
    def delete(self, build_id):
        with self.sessions() as db:
            row=db.get(BuildRecord,build_id)
            if row: db.delete(row); db.commit()
            return row is not None
