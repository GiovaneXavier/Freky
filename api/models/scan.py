import uuid
from datetime import datetime
from sqlalchemy import String, Float, DateTime, JSON, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from models.database import Base
from core.rules import Decision


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Arquivo de origem (do Xport)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    image_path: Mapped[str] = mapped_column(String, nullable=False)
    annotated_image_path: Mapped[str | None] = mapped_column(String, nullable=True)

    # Resultado da deteccao
    decision: Mapped[str] = mapped_column(
        SAEnum(Decision, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    detections: Mapped[list] = mapped_column(JSON, default=list)
    processing_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Auditoria do operador
    operator_id: Mapped[str | None] = mapped_column(String, nullable=True)
    operator_feedback: Mapped[str | None] = mapped_column(String, nullable=True)
    feedback_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
