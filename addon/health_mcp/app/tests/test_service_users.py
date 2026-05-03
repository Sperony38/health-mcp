from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from health_mcp.models import Base, LabReport, Patient
from health_mcp.service import HealthService


class FakeDatabase:
    def __init__(self) -> None:
        self._engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self._engine)
        self._session_factory = sessionmaker(
            bind=self._engine,
            autoflush=False,
            expire_on_commit=False,
        )

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


def test_list_service_users_returns_owner_summaries():
    database = FakeDatabase()
    service = HealthService(database)

    with database.session() as session:
        owner_a_patient_1 = Patient(
            owner_user_id="owner-a",
            owner_display_name="Alice",
            external_id="alice-1",
            full_name="Alice One",
            sex="female",
            birth_date=date(2010, 1, 1),
        )
        owner_a_patient_2 = Patient(
            owner_user_id="owner-a",
            owner_display_name="Alice",
            external_id="alice-2",
            full_name="Alice Two",
        )
        owner_b_patient = Patient(
            owner_user_id="owner-b",
            owner_display_name="Bob",
            external_id="bob-1",
            full_name="Bob One",
        )
        session.add_all([owner_a_patient_1, owner_a_patient_2, owner_b_patient])
        session.flush()

        session.add_all(
            [
                LabReport(
                    patient_id=owner_a_patient_1.id,
                    source_system="manual",
                    collected_at=datetime(2025, 1, 1, 9, 0, 0),
                ),
                LabReport(
                    patient_id=owner_a_patient_2.id,
                    source_system="manual",
                    collected_at=datetime(2025, 2, 1, 9, 0, 0),
                ),
                LabReport(
                    patient_id=owner_b_patient.id,
                    source_system="manual",
                    collected_at=datetime(2025, 3, 1, 9, 0, 0),
                ),
            ]
        )

    summaries = service.list_service_users()

    assert [item.owner_user_id for item in summaries] == ["owner-b", "owner-a"]
    assert summaries[0].owner_display_name == "Bob"
    assert summaries[0].patient_count == 1
    assert summaries[0].report_count == 1
    assert summaries[0].last_report_at == datetime(2025, 3, 1, 9, 0, 0)
    assert summaries[1].owner_display_name == "Alice"
    assert summaries[1].patient_count == 2
    assert summaries[1].report_count == 2
    assert summaries[1].last_report_at == datetime(2025, 2, 1, 9, 0, 0)


def test_list_service_users_supports_query_filter():
    database = FakeDatabase()
    service = HealthService(database)

    with database.session() as session:
        session.add_all(
            [
                Patient(owner_user_id="local-family", owner_display_name="Local Family", external_id="a"),
                Patient(owner_user_id="demo-user", owner_display_name="Demo", external_id="b"),
            ]
        )

    filtered = service.list_service_users(query="local")

    assert [item.owner_user_id for item in filtered] == ["local-family"]
