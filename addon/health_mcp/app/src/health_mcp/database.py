from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings
from .models import Base


class Database:
    def __init__(self, settings: Settings) -> None:
        self._engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            future=True,
        )
        self._session_factory = sessionmaker(
            bind=self._engine,
            autoflush=False,
            expire_on_commit=False,
        )

    @property
    def engine(self):
        return self._engine

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def initialize_schema(self) -> None:
        Base.metadata.create_all(self._engine)

    def ping(self) -> None:
        with self.session() as session:
            session.execute(text("SELECT 1"))

