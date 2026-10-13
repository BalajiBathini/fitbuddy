"""
Database bootstrap: engine creation, auto-create-on-first-launch, and a
minimal schema-version migration mechanism.

The app never ships the production DB inside the install directory (Section
17) - it always lives under the per-user app-data directory resolved by
app.config.get_db_path().
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import sessionmaker

from app.database.models import Base, SchemaVersion

logger = logging.getLogger("fitbuddy.database")

CURRENT_SCHEMA_VERSION = 1


class Database:
    """Thin wrapper owning the SQLAlchemy engine + session factory."""

    def __init__(self, db_path: Path | str, echo: bool = False) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            echo=echo,
            future=True,
            connect_args={"check_same_thread": False},
        )
        self._session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self._init_pragmas()
        self.create_all()
        self._run_migrations()

    def _init_pragmas(self) -> None:
        """Enable WAL mode + foreign keys for durability & concurrent reads."""
        with self.engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
            conn.exec_driver_sql("PRAGMA foreign_keys=ON;")
            conn.exec_driver_sql("PRAGMA synchronous=NORMAL;")

    def create_all(self) -> None:
        Base.metadata.create_all(self.engine)
        logger.info("Database schema ensured at %s", self.db_path)

    def _run_migrations(self) -> None:
        """
        Minimal forward-only migration runner.

        Real migrations (adding columns, etc.) would be added as numbered
        steps here, gated on the stored schema_version row. For the MVP
        there is only version 1, so this just seeds the version row.
        """
        with self.session() as s:
            row = s.execute(select(SchemaVersion)).scalar_one_or_none()
            if row is None:
                s.add(SchemaVersion(id=1, version=CURRENT_SCHEMA_VERSION))
                s.commit()
                logger.info("Initialized schema_version=%d", CURRENT_SCHEMA_VERSION)
            elif row.version < CURRENT_SCHEMA_VERSION:
                # Future migration steps would run here, incrementing row.version.
                row.version = CURRENT_SCHEMA_VERSION
                s.commit()
                logger.info("Migrated schema to version=%d", CURRENT_SCHEMA_VERSION)

    @contextmanager
    def session(self) -> Iterator[OrmSession]:
        """Context-managed session with automatic rollback on error."""
        session = self._session_factory()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


_db_instance: Database | None = None


def get_database(db_path: Path | str | None = None, echo: bool = False) -> Database:
    """Process-wide singleton accessor (a real desktop agent is single-process)."""
    global _db_instance
    if _db_instance is None:
        if db_path is None:
            from app.config import get_db_path

            db_path = get_db_path()
        _db_instance = Database(db_path, echo=echo)
    return _db_instance


def reset_database_singleton() -> None:
    """Test-only helper to force a fresh Database on next get_database() call."""
    global _db_instance
    _db_instance = None
