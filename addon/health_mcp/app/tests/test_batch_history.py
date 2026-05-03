from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from health_mcp.models import Base, Indicator, IndicatorReferenceRange, LabReport, LabResult, Patient
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


def test_get_patient_indicators_history_returns_batch_in_requested_order():
    database = FakeDatabase()
    service = HealthService(database)

    with database.session() as session:
        patient = Patient(
            owner_user_id="family-1",
            owner_display_name="Family One",
            external_id="patient-1",
            full_name="Patient One",
            sex="male",
            birth_date=date(1993, 12, 29),
        )
        alt = Indicator(code="alt", name="ALT", canonical_unit="U/L")
        alt.reference_ranges.append(
            IndicatorReferenceRange(sex="male", upper_bound=Decimal("41.0"), priority=10)
        )
        ast = Indicator(code="ast", name="AST", canonical_unit="U/L")
        ast.reference_ranges.append(
            IndicatorReferenceRange(sex="male", upper_bound=Decimal("40.0"), priority=10)
        )
        ggt = Indicator(code="ggt", name="GGT", canonical_unit="U/L")
        session.add_all([patient, alt, ast, ggt])
        session.flush()

        reports = [
            LabReport(patient_id=patient.id, source_system="manual", collected_at=datetime(2024, 12, 21, 9, 0, 0)),
            LabReport(patient_id=patient.id, source_system="manual", collected_at=datetime(2025, 5, 15, 9, 0, 0)),
            LabReport(patient_id=patient.id, source_system="manual", collected_at=datetime(2026, 1, 4, 9, 0, 0)),
        ]
        session.add_all(reports)
        session.flush()

        session.add_all(
            [
                LabResult(report_id=reports[0].id, indicator_id=alt.id, measured_value=Decimal("127.0"), unit="U/L"),
                LabResult(report_id=reports[1].id, indicator_id=alt.id, measured_value=Decimal("316.0"), unit="U/L"),
                LabResult(report_id=reports[2].id, indicator_id=alt.id, measured_value=Decimal("67.0"), unit="U/L"),
                LabResult(report_id=reports[2].id, indicator_id=ast.id, measured_value=Decimal("30.0"), unit="U/L"),
            ]
        )

    batch = service.get_patient_indicators_history(
        owner_user_id="family-1",
        patient_external_id="patient-1",
        indicator_codes=["ggt", "ast", "alt", "missing-code", "alt"],
        limit=2,
    )

    assert batch.owner_user_id == "family-1"
    assert batch.patient_external_id == "patient-1"
    assert [item.indicator_code for item in batch.indicators] == ["ggt", "ast", "alt"]
    assert batch.missing_indicator_codes == ["missing-code"]

    ggt_view, ast_view, alt_view = batch.indicators
    assert ggt_view.points == []
    assert len(ast_view.points) == 1
    assert ast_view.points[0].value == 30.0
    assert ast_view.points[0].status.value == "normal"

    assert len(alt_view.points) == 2
    assert [point.value for point in alt_view.points] == [67.0, 316.0]
    assert [point.status.value for point in alt_view.points] == ["high", "high"]
