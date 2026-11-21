from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Index,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Auction(Base):
    __tablename__ = "auctions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(40), default="setad_main_estate", nullable=False)
    source_party_id: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False, default="movable", server_default="movable")
    has_keyword_match: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    item_title: Mapped[str | None] = mapped_column(Text)
    item_reference_no: Mapped[str | None] = mapped_column(String(120))
    asset_type: Mapped[str | None] = mapped_column(String(180))
    price_type: Mapped[str | None] = mapped_column(String(40))
    rent_duration_months: Mapped[int | None] = mapped_column()
    rent_duration_days: Mapped[int | None] = mapped_column()
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
    site_show_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    site_show_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    publish_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    publish_finish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    winner_announce_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opening_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_modify_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trust_opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    base_total_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    trust_amount: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    total_volume_m3: Mapped[Decimal | None] = mapped_column(Numeric(20, 3))
    money_unit: Mapped[str | None] = mapped_column(String(30))
    source_url: Mapped[str | None] = mapped_column(Text)
    matched_keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("source", "source_party_id", name="uq_auctions_source_party"),
        Index("ix_auctions_deadline", "proposal_deadline"),
        Index("ix_auctions_site_show_start", "site_show_start_at"),
        Index("ix_auctions_publish_start", "publish_start_at"),
        Index("ix_auctions_location", "province", "city"),
        Index("ix_auctions_base_total_price", "base_total_price"),
        Index("ix_auctions_state", "state"),
        Index("ix_auctions_category", "category"),
        Index("ix_auctions_category_match", "category", "has_keyword_match"),
    )


class Tender(Base):
    __tablename__ = "tenders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(40), default="setad_tender", nullable=False)
    source_tender_id: Mapped[str] = mapped_column(String(120), nullable=False)
    has_keyword_match: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    matched_keywords: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default="'[]'::jsonb")
    tender_number: Mapped[str | None] = mapped_column(String(120))
    title: Mapped[str | None] = mapped_column(Text)
    tender_type: Mapped[str | None] = mapped_column(String(120))
    type_name: Mapped[str | None] = mapped_column(String(240))
    organization: Mapped[str | None] = mapped_column(Text)
    province: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str | None] = mapped_column(String(120))
    public_notification_date: Mapped[str | None] = mapped_column(String(40))
    documents_deadline_date: Mapped[str | None] = mapped_column(String(40))
    proposal_deadline_date: Mapped[str | None] = mapped_column(String(40))
    opening_date: Mapped[str | None] = mapped_column(String(40))
    public_notification_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    documents_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    proposal_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opening_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("source", "source_tender_id", name="uq_tenders_source_tender"),
        Index("ix_tenders_number", "tender_number"),
        Index("ix_tenders_notification_date", "public_notification_date"),
        Index("ix_tenders_proposal_deadline", "proposal_deadline_date"),
        Index("ix_tenders_public_notification_at", "public_notification_at"),
        Index("ix_tenders_proposal_deadline_at", "proposal_deadline_at"),
        Index("ix_tenders_location", "province", "city"),
        Index("ix_tenders_state_type", "state", "type_name"),
        Index("ix_tenders_keyword_match", "has_keyword_match"),
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
    kind: Mapped[str | None] = mapped_column(String(20))
    category: Mapped[str | None] = mapped_column(String(24))

    __table_args__ = (
        Index("ix_ingestion_runs_scope_finished", "kind", "category", "status", "finished_at"),
    )


class AppSetting(Base):
    """Small, persistent site-wide configuration values."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
