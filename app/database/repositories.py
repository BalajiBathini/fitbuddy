"""
Repository layer. Each repository wraps CRUD + query operations for one
table so that service-layer code (app/fitness, app/agent) never touches
SQLAlchemy directly. All repositories take a Database instance and open
their own short-lived sessions per call, which keeps them safe to use from
scheduler callbacks and Qt slots alike.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any, Sequence

from sqlalchemy import select

from app.database.database import Database
from app.database.models import (
    ActivityLog,
    BreakLog,
    DailySummary,
    Session,
    Setting,
    WaterLog,
)


class SettingsRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def get_all(self) -> dict[str, Any]:
        with self.db.session() as s:
            rows = s.execute(select(Setting)).scalars().all()
            return {row.key: json.loads(row.value) for row in rows}

    def get(self, key: str, default: Any = None) -> Any:
        with self.db.session() as s:
            row = s.get(Setting, key)
            if row is None:
                return default
            return json.loads(row.value)

    def set(self, key: str, value: Any) -> None:
        with self.db.session() as s:
            row = s.get(Setting, key)
            encoded = json.dumps(value)
            if row is None:
                s.add(Setting(key=key, value=encoded))
            else:
                row.value = encoded
            s.commit()

    def set_many(self, values: dict[str, Any]) -> None:
        with self.db.session() as s:
            for key, value in values.items():
                row = s.get(Setting, key)
                encoded = json.dumps(value)
                if row is None:
                    s.add(Setting(key=key, value=encoded))
                else:
                    row.value = encoded
            s.commit()

    def seed_defaults(self, defaults: dict[str, Any]) -> None:
        """Insert any default keys that aren't already present. Never overwrites."""
        with self.db.session() as s:
            existing = {row.key for row in s.execute(select(Setting)).scalars().all()}
            for key, value in defaults.items():
                if key not in existing:
                    s.add(Setting(key=key, value=json.dumps(value)))
            s.commit()


class SessionRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def start_session(self, started_at: dt.datetime) -> int:
        with self.db.session() as s:
            session = Session(started_at=started_at)
            s.add(session)
            s.commit()
            return session.id

    def end_session(
        self,
        session_id: int,
        ended_at: dt.datetime,
        active_seconds: int,
        idle_seconds: int,
        end_reason: str,
    ) -> None:
        with self.db.session() as s:
            row = s.get(Session, session_id)
            if row is None:
                return
            row.ended_at = ended_at
            row.active_seconds = active_seconds
            row.idle_seconds = idle_seconds
            row.end_reason = end_reason
            s.commit()

    def get_open_session(self) -> Session | None:
        with self.db.session() as s:
            stmt = select(Session).where(Session.ended_at.is_(None)).order_by(Session.started_at.desc())
            return s.execute(stmt).scalars().first()

    def sessions_between(self, start: dt.datetime, end: dt.datetime) -> Sequence[Session]:
        with self.db.session() as s:
            stmt = select(Session).where(Session.started_at >= start, Session.started_at < end)
            return s.execute(stmt).scalars().all()


class ActivityRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def log_activity(
        self,
        activity_type: str,
        target: float,
        completed: float,
        unit: str,
        duration_seconds: int = 0,
        source: str = "manual",
        skipped: bool = False,
        timestamp: dt.datetime | None = None,
    ) -> int:
        with self.db.session() as s:
            entry = ActivityLog(
                activity_type=activity_type,
                target=target,
                completed=completed,
                unit=unit,
                duration_seconds=duration_seconds,
                source=source,
                skipped=skipped,
                timestamp=timestamp or dt.datetime.utcnow(),
            )
            s.add(entry)
            s.commit()
            return entry.id

    def activities_between(self, start: dt.datetime, end: dt.datetime) -> Sequence[ActivityLog]:
        with self.db.session() as s:
            stmt = select(ActivityLog).where(
                ActivityLog.timestamp >= start, ActivityLog.timestamp < end
            ).order_by(ActivityLog.timestamp)
            return s.execute(stmt).scalars().all()

    def count_today(self, activity_type: str | None, start_of_day: dt.datetime) -> int:
        with self.db.session() as s:
            stmt = select(ActivityLog).where(ActivityLog.timestamp >= start_of_day, ActivityLog.skipped.is_(False))
            if activity_type:
                stmt = stmt.where(ActivityLog.activity_type == activity_type)
            return len(s.execute(stmt).scalars().all())


class WaterRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def log_water(self, amount_ml: int, source: str = "manual", timestamp: dt.datetime | None = None) -> int:
        with self.db.session() as s:
            entry = WaterLog(amount_ml=amount_ml, source=source, timestamp=timestamp or dt.datetime.utcnow())
            s.add(entry)
            s.commit()
            return entry.id

    def total_between(self, start: dt.datetime, end: dt.datetime) -> int:
        with self.db.session() as s:
            stmt = select(WaterLog).where(WaterLog.timestamp >= start, WaterLog.timestamp < end)
            rows = s.execute(stmt).scalars().all()
            return sum(r.amount_ml for r in rows)

    def last_entry_time(self) -> dt.datetime | None:
        with self.db.session() as s:
            stmt = select(WaterLog).order_by(WaterLog.timestamp.desc())
            row = s.execute(stmt).scalars().first()
            return row.timestamp if row else None


class BreakRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def start_break(self, planned_duration_minutes: int) -> int:
        with self.db.session() as s:
            entry = BreakLog(
                started_at=dt.datetime.utcnow(),
                planned_duration_minutes=planned_duration_minutes,
            )
            s.add(entry)
            s.commit()
            return entry.id

    def finish_break(self, break_id: int, actual_duration_seconds: int, completed: bool) -> None:
        with self.db.session() as s:
            row = s.get(BreakLog, break_id)
            if row is None:
                return
            row.ended_at = dt.datetime.utcnow()
            row.actual_duration_seconds = actual_duration_seconds
            row.completed = completed
            s.commit()

    def skip_break(self, break_id: int) -> None:
        with self.db.session() as s:
            row = s.get(BreakLog, break_id)
            if row is None:
                return
            row.ended_at = dt.datetime.utcnow()
            row.skipped = True
            s.commit()

    def breaks_between(self, start: dt.datetime, end: dt.datetime) -> Sequence[BreakLog]:
        with self.db.session() as s:
            stmt = select(BreakLog).where(BreakLog.started_at >= start, BreakLog.started_at < end)
            return s.execute(stmt).scalars().all()

    def last_break_time(self) -> dt.datetime | None:
        with self.db.session() as s:
            stmt = select(BreakLog).order_by(BreakLog.started_at.desc())
            row = s.execute(stmt).scalars().first()
            return row.started_at if row else None


class DailySummaryRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert(self, date_str: str, **fields: Any) -> None:
        with self.db.session() as s:
            stmt = select(DailySummary).where(DailySummary.date == date_str)
            row = s.execute(stmt).scalars().first()
            if row is None:
                row = DailySummary(date=date_str, **fields)
                s.add(row)
            else:
                for k, v in fields.items():
                    setattr(row, k, v)
            s.commit()

    def get(self, date_str: str) -> DailySummary | None:
        with self.db.session() as s:
            stmt = select(DailySummary).where(DailySummary.date == date_str)
            return s.execute(stmt).scalars().first()

    def get_range(self, start_date: str, end_date: str) -> Sequence[DailySummary]:
        with self.db.session() as s:
            stmt = select(DailySummary).where(
                DailySummary.date >= start_date, DailySummary.date <= end_date
            ).order_by(DailySummary.date)
            return s.execute(stmt).scalars().all()
