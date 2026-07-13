from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class DailySummarySetting(Base):
    __tablename__ = "daily_summary_settings"

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_daily_summary_settings_user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    hour: Mapped[int] = mapped_column(
        Integer,
        default=20,
        nullable=False,
    )

    minute: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    timezone: Mapped[str] = mapped_column(
        String(100),
        default="America/New_York",
        nullable=False,
    )

    last_sent_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship()