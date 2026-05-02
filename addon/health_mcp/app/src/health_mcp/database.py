from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
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
        self._apply_schema_upgrades()

    def ping(self) -> None:
        with self.session() as session:
            session.execute(text("SELECT 1"))

    def _apply_schema_upgrades(self) -> None:
        inspector = inspect(self._engine)
        table_names = set(inspector.get_table_names())
        with self._engine.begin() as connection:
            if "indicators" in table_names:
                indicator_columns = {column["name"] for column in inspector.get_columns("indicators")}
                indicator_uniques = {
                    constraint["name"]
                    for constraint in inspector.get_unique_constraints("indicators")
                    if constraint.get("name")
                }
                if "standard_system" not in indicator_columns:
                    connection.execute(text("ALTER TABLE indicators ADD COLUMN standard_system VARCHAR(32) NULL"))
                if "standard_code" not in indicator_columns:
                    connection.execute(text("ALTER TABLE indicators ADD COLUMN standard_code VARCHAR(64) NULL"))
                if "uq_indicators_standard_identity" not in indicator_uniques:
                    connection.execute(
                        text(
                            "ALTER TABLE indicators ADD CONSTRAINT uq_indicators_standard_identity "
                            "UNIQUE (standard_system, standard_code)"
                        )
                    )

        if "lab_results" not in table_names:
            return

        existing_columns = {column["name"] for column in inspector.get_columns("lab_results")}
        statements: list[str] = []

        if "source_name" not in existing_columns:
            statements.append("ALTER TABLE lab_results ADD COLUMN source_name VARCHAR(255) NULL")
        if "raw_value" not in existing_columns:
            statements.append("ALTER TABLE lab_results ADD COLUMN raw_value VARCHAR(64) NULL")
        if "value_operator" not in existing_columns:
            statements.append("ALTER TABLE lab_results ADD COLUMN value_operator VARCHAR(8) NULL")
        if "reference_text" not in existing_columns:
            statements.append("ALTER TABLE lab_results ADD COLUMN reference_text TEXT NULL")

        if not statements:
            return

        with self._engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))
