"""
SQLAlchemy ORM models for FitBuddy's local SQLite store.

Tables (per Section 17 of the spec):
    settings          - key/value user settings
    sessions          - active-usage sessions (start/end, active vs idle)
    activity_logs     - completed fitness activities (push-ups, breaks, etc.)
    water_logs        - water intake entries
    break_logs        - break start/finish/skip records
    daily_summaries   - precomputed daily rollups for fast dashboard reads
    schema_version     - single-row table for migration tracking
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def utcnow() -> dt.datetime:
    return dt.datetime.utcnow()


class SchemaVersion(Base):
    """Single-row table tracking the current schema version for migrations."""

    __tablename__ = "schema_version"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(String(2048), nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Session(Base):
    """A contiguous block of active computer usage (idle gaps split sessions)."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, index=True)
    ended_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    active_seconds: Mapped[int] = mapped_column(Integer, default=0)
    idle_seconds: Mapped[int] = mapped_column(Integer, default=0)
    end_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # e.g. "idle_timeout", "lock", "sleep", "shutdown"


class ActivityLog(Base):
    """A completed (or skipped) fitness activity, per Section 16."""

    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    activity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target: Mapped[float] = mapped_column(Float, default=0)
    completed: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[str] = mapped_column(String(32), default="reps")
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(32), default="manual")
    # source: "manual" | "reminder" | "creature_menu"
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)


class WaterLog(Base):
    __tablename__ = "water_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    amount_ml: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)
    source: Mapped[str] = mapped_column(String(32), default="manual")


class BreakLog(Base):
    __tablename__ = "break_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)
    ended_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    planned_duration_minutes: Mapped[int] = mapped_column(Integer, default=5)
    actual_duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)


class DailySummary(Base):
    """Precomputed per-day rollup, refreshed by statistics_service."""

    __tablename__ = "daily_summaries"
    __table_args__ = (UniqueConstraint("date", name="uq_daily_summary_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    active_seconds: Mapped[int] = mapped_column(Integer, default=0)
    idle_seconds: Mapped[int] = mapped_column(Integer, default=0)
    breaks_count: Mapped[int] = mapped_column(Integer, default=0)
    break_seconds: Mapped[int] = mapped_column(Integer, default=0)
    water_ml: Mapped[int] = mapped_column(Integer, default=0)
    exercise_reps: Mapped[int] = mapped_column(Integer, default=0)
    walking_minutes: Mapped[int] = mapped_column(Integer, default=0)
    daily_score: Mapped[float] = mapped_column(Float, default=0)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
