from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    mentions: Mapped[list["Mention"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


class Mention(Base):
    __tablename__ = "mentions"
    __table_args__ = (
        UniqueConstraint("owner_id", "url", name="uq_mention_owner_url"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    brand: Mapped[str] = mapped_column(String(255), index=True)
    source: Mapped[str] = mapped_column(String(100))
    text: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(2048))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    sentiment: Mapped[str | None] = mapped_column(String(32))
    topic: Mapped[str | None] = mapped_column(String(255))
    urgency: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    owner: Mapped[User] = relationship(back_populates="mentions")
