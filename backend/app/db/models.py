from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from sqlalchemy import BigInteger, DateTime, Index, JSON, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class Auction(Base):
    __tablename__ = "auctions"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(40), default="setad_main_estate", nullable=False)
    source_party_id: Mapped[str] = mapped_column(String(120), nullable=False)
    auction_id: Mapped[str | None] = mapped_column(String(120))
    auction_no: Mapped[str | None] = mapped_column(String(120))
    auction_reference_no: Mapped[str | None] = mapped_column(String(120))
    title: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    organization: Mapped[str | None] = mapped_column(Text)
    province: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(200))
    state: Mapped[str | None] = mapped_column(String(100))
    proposal_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    proposal_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    document_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    base_total_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    trust_amount: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    total_volume_m3: Mapped[Decimal | None] = mapped_column(Numeric(20, 3))
    money_unit: Mapped[str | None] = mapped_column(String(30))
    source_url: Mapped[str | None] = mapped_column(Text)
    matched_keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint("source", "source_party_id", name="uq_auctions_source_party"),
        Index("ix_auctions_deadline", "proposal_deadline"),
    )

class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="running")
    fetched: Mapped[int] = mapped_column(BigInteger, default=0)
    matched: Mapped[int] = mapped_column(BigInteger, default=0)
    stored: Mapped[int] = mapped_column(BigInteger, default=0)
    skipped_expired: Mapped[int] = mapped_column(BigInteger, default=0)
    skipped_unknown_deadline: Mapped[int] = mapped_column(BigInteger, default=0)
    error: Mapped[str | None] = mapped_column(Text)
