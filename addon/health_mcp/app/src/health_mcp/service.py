from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from math import inf

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from .database import Database
from .models import Indicator, IndicatorReferenceRange, LabReport, LabResult, Patient
from .schemas import (
    ImportLabReportResult,
    ImportedLabResult,
    IndicatorCatalogEntry,
    IndicatorHistoryPoint,
    IndicatorHistoryView,
    IndicatorStatus,
    IndicatorSummary,
    IndicatorUpsertInput,
    LabReportInput,
    ReferenceRangeInput,
    ReferenceRangeView,
    Sex,
    UserPatientSummary,
)


class HealthMcpError(RuntimeError):
    pass


class NotFoundError(HealthMcpError):
    pass


class DuplicateReportError(HealthMcpError):
    pass


def _age_years_to_days(value: float | None) -> int | None:
    if value is None:
        return None
    return int(round(value * 365.25))


def _days_to_years(value: int | None) -> float | None:
    if value is None:
        return None
    return round(value / 365.25, 4)


def _decimal_or_none(value: float | Decimal | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _float_or_none(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _calculate_age_days(birth_date: date | None, collected_at: datetime) -> int | None:
    if birth_date is None:
        return None
    return (collected_at.date() - birth_date).days


@dataclass(frozen=True)
class RangeMatch:
    range_row: IndicatorReferenceRange
    score: tuple[int, int, float, int]


@dataclass(frozen=True)
class ComparableRange:
    lower_bound: Decimal | None
    upper_bound: Decimal | None
    note: str | None = None
    sex: str | None = None
    min_age_days: int | None = None
    max_age_days: int | None = None
    priority: int = 0


def _range_matches(range_row: IndicatorReferenceRange, sex: str | None, age_days: int | None) -> bool:
    if range_row.sex and sex and range_row.sex != sex:
        return False
    if range_row.sex and not sex:
        return False
    if range_row.min_age_days is not None and age_days is None:
        return False
    if range_row.max_age_days is not None and age_days is None:
        return False
    if range_row.min_age_days is not None and age_days is not None and age_days < range_row.min_age_days:
        return False
    if range_row.max_age_days is not None and age_days is not None and age_days > range_row.max_age_days:
        return False
    return True


def select_best_reference_range(
    ranges: list[IndicatorReferenceRange],
    sex: str | None,
    age_days: int | None,
) -> IndicatorReferenceRange | None:
    matches: list[RangeMatch] = []
    for range_row in ranges:
        if not _range_matches(range_row, sex, age_days):
            continue

        sex_specific = 1 if range_row.sex else 0
        bounded_count = int(range_row.min_age_days is not None) + int(range_row.max_age_days is not None)
        if range_row.min_age_days is None or range_row.max_age_days is None:
            span = inf
        else:
            span = float(range_row.max_age_days - range_row.min_age_days)

        matches.append(
            RangeMatch(
                range_row=range_row,
                score=(range_row.priority, sex_specific, bounded_count, -span),
            )
        )

    if not matches:
        return None

    matches.sort(key=lambda item: item.score, reverse=True)
    return matches[0].range_row


def classify_value(value: Decimal, range_row: IndicatorReferenceRange | ComparableRange | None) -> IndicatorStatus:
    if range_row is None:
        return IndicatorStatus.unknown
    if range_row.lower_bound is not None and value < range_row.lower_bound:
        return IndicatorStatus.low
    if range_row.upper_bound is not None and value > range_row.upper_bound:
        return IndicatorStatus.high
    return IndicatorStatus.normal


class HealthService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def initialize_schema(self) -> None:
        self.database.initialize_schema()

    def ping(self) -> None:
        self.database.ping()

    def upsert_indicator(self, payload: IndicatorUpsertInput) -> IndicatorCatalogEntry:
        with self.database.session() as session:
            indicator = self._find_indicator_for_write(
                session,
                payload.code,
                payload.standard_system,
                payload.standard_code,
            )

            if indicator is None:
                indicator = Indicator(code=payload.code, name=payload.name)
                session.add(indicator)

            indicator.code = payload.code
            indicator.name = payload.name
            indicator.standard_system = payload.standard_system
            indicator.standard_code = payload.standard_code
            indicator.canonical_unit = payload.canonical_unit
            indicator.description = payload.description

            if payload.replace_reference_ranges:
                indicator.reference_ranges.clear()

            if payload.reference_ranges:
                indicator.reference_ranges.extend(
                    self._build_reference_range_rows(payload.reference_ranges)
                )

            session.flush()
            return self._indicator_entry_from_model(indicator)

    def list_indicators(self, query: str | None = None, limit: int = 50) -> list[IndicatorSummary]:
        effective_limit = max(1, min(limit, 200))
        with self.database.session() as session:
            statement = select(Indicator).options(selectinload(Indicator.reference_ranges)).order_by(Indicator.code.asc())
            if query:
                like = f"%{query.lower()}%"
                statement = statement.where(
                    func.lower(Indicator.code).like(like)
                    | func.lower(Indicator.name).like(like)
                    | func.lower(func.coalesce(Indicator.standard_code, "")).like(like)
                )
            rows = session.scalars(statement.limit(effective_limit)).all()
            return [
                IndicatorSummary(
                    code=row.code,
                    name=row.name,
                    standard_system=row.standard_system,
                    standard_code=row.standard_code,
                    canonical_unit=row.canonical_unit,
                    reference_range_count=len(row.reference_ranges),
                )
                for row in rows
            ]

    def get_indicator(self, code: str) -> IndicatorCatalogEntry:
        with self.database.session() as session:
            indicator = session.scalar(
                select(Indicator)
                .options(selectinload(Indicator.reference_ranges))
                .where(func.lower(Indicator.code) == code.lower())
            )
            if indicator is None:
                raise NotFoundError(f"Indicator '{code}' was not found")
            return self._indicator_entry_from_model(indicator)

    def import_lab_report(self, payload: LabReportInput) -> ImportLabReportResult:
        with self.database.session() as session:
            patient = session.scalar(
                select(Patient).where(
                    Patient.owner_user_id == payload.owner_user_id,
                    Patient.external_id == payload.patient_external_id,
                )
            )
            if patient is None:
                patient = Patient(
                    owner_user_id=payload.owner_user_id,
                    external_id=payload.patient_external_id,
                )
                session.add(patient)

            patient.owner_user_id = payload.owner_user_id
            patient.owner_display_name = payload.owner_display_name or patient.owner_display_name
            patient.full_name = payload.patient_name or patient.full_name
            patient.birth_date = payload.patient_birth_date or patient.birth_date
            patient.sex = payload.patient_sex.value if payload.patient_sex else patient.sex

            session.flush()

            if payload.external_report_id:
                existing_report = session.scalar(
                    select(LabReport).where(
                        LabReport.patient_id == patient.id,
                        LabReport.source_system == payload.source_system,
                        LabReport.external_report_id == payload.external_report_id,
                    )
                )
                if existing_report is not None:
                    raise DuplicateReportError(
                        f"Report '{payload.external_report_id}' from '{payload.source_system}' already exists for this patient"
                    )

            report = LabReport(
                patient=patient,
                source_system=payload.source_system,
                external_report_id=payload.external_report_id,
                collected_at=payload.collected_at,
                notes=payload.notes,
            )
            session.add(report)
            session.flush()

            imported_results: list[ImportedLabResult] = []
            patient_age_days = _calculate_age_days(patient.birth_date, report.collected_at)

            for item in payload.results:
                indicator = self._find_indicator_for_import(
                    session,
                    item.indicator_code,
                    item.standard_system,
                    item.standard_code,
                )
                if indicator is None:
                    if not item.indicator_name:
                        raise NotFoundError(
                            f"Indicator '{item.indicator_code}' does not exist and indicator_name was not provided"
                        )
                    indicator = Indicator(
                        code=item.indicator_code,
                        name=item.indicator_name,
                        standard_system=item.standard_system,
                        standard_code=item.standard_code,
                        canonical_unit=item.unit,
                    )
                    session.add(indicator)
                    session.flush()
                else:
                    if item.standard_system and item.standard_code:
                        self._apply_indicator_standard_identity(
                            indicator,
                            item.standard_system,
                            item.standard_code,
                        )

                result_value = Decimal(str(item.value))
                captured_range = self._captured_range_from_bounds(
                    item.captured_lower_bound,
                    item.captured_upper_bound,
                    item.reference_text,
                )
                result = LabResult(
                    report=report,
                    indicator=indicator,
                    source_name=item.source_name or item.indicator_name,
                    raw_value=item.raw_value,
                    value_operator=item.value_operator,
                    measured_value=result_value,
                    unit=item.unit,
                    captured_lower_bound=_decimal_or_none(item.captured_lower_bound),
                    captured_upper_bound=_decimal_or_none(item.captured_upper_bound),
                    reference_text=item.reference_text,
                    flag=item.flag,
                    comment=item.comment,
                )
                session.add(result)

                matched_range = select_best_reference_range(
                    indicator.reference_ranges,
                    patient.sex,
                    patient_age_days,
                )
                effective_range = matched_range or captured_range

                warnings: list[str] = []
                if indicator.canonical_unit and item.unit and indicator.canonical_unit != item.unit:
                    warnings.append(
                        f"Result unit '{item.unit}' differs from catalog unit '{indicator.canonical_unit}'. No conversion was applied."
                    )

                imported_results.append(
                    ImportedLabResult(
                        indicator_code=indicator.code,
                        indicator_name=indicator.name,
                        standard_system=indicator.standard_system,
                        standard_code=indicator.standard_code,
                        source_name=result.source_name,
                        value=float(result_value),
                        raw_value=result.raw_value,
                        unit=item.unit or indicator.canonical_unit,
                        status=classify_value(result_value, effective_range),
                        reference_range=self._reference_range_view_any(effective_range) if effective_range else None,
                        reference_text=result.reference_text,
                        warnings=warnings,
                    )
                )

            session.flush()
            return ImportLabReportResult(
                report_id=report.id,
                owner_user_id=patient.owner_user_id,
                patient_external_id=patient.external_id,
                source_system=payload.source_system,
                collected_at=payload.collected_at,
                imported_count=len(imported_results),
                results=imported_results,
            )

    def get_patient_indicator_history(
        self,
        owner_user_id: str,
        patient_external_id: str,
        indicator_code: str,
        limit: int = 20,
    ) -> IndicatorHistoryView:
        effective_limit = max(1, min(limit, 200))
        with self.database.session() as session:
            patient = session.scalar(
                select(Patient).where(
                    Patient.owner_user_id == owner_user_id,
                    Patient.external_id == patient_external_id,
                )
            )
            if patient is None:
                raise NotFoundError(
                    f"Patient '{patient_external_id}' for user '{owner_user_id}' was not found"
                )

            indicator = session.scalar(
                select(Indicator)
                .options(selectinload(Indicator.reference_ranges))
                .where(func.lower(Indicator.code) == indicator_code.lower())
            )
            if indicator is None:
                raise NotFoundError(f"Indicator '{indicator_code}' was not found")

            rows = session.execute(
                select(LabResult, LabReport)
                .join(LabReport, LabResult.report_id == LabReport.id)
                .where(
                    LabReport.patient_id == patient.id,
                    LabResult.indicator_id == indicator.id,
                )
                .order_by(LabReport.collected_at.desc())
                .limit(effective_limit)
            ).all()

            points: list[IndicatorHistoryPoint] = []
            for result, report in rows:
                matched_range = select_best_reference_range(
                    indicator.reference_ranges,
                    patient.sex,
                    _calculate_age_days(patient.birth_date, report.collected_at),
                )
                effective_range = matched_range or self._captured_range_from_result(result)
                points.append(
                    IndicatorHistoryPoint(
                        report_id=report.id,
                        collected_at=report.collected_at,
                        source_system=report.source_system,
                        external_report_id=report.external_report_id,
                        standard_system=indicator.standard_system,
                        standard_code=indicator.standard_code,
                        source_name=result.source_name,
                        value=float(result.measured_value),
                        raw_value=result.raw_value,
                        unit=result.unit or indicator.canonical_unit,
                        status=classify_value(result.measured_value, effective_range),
                        reference_range=self._reference_range_view_any(effective_range) if effective_range else None,
                        reference_text=result.reference_text,
                    )
                )

            return IndicatorHistoryView(
                owner_user_id=patient.owner_user_id,
                patient_external_id=patient.external_id,
                patient_name=patient.full_name,
                indicator_code=indicator.code,
                indicator_name=indicator.name,
                standard_system=indicator.standard_system,
                standard_code=indicator.standard_code,
                canonical_unit=indicator.canonical_unit,
                points=points,
            )

    def list_user_patients(
        self,
        owner_user_id: str,
        query: str | None = None,
        limit: int = 50,
    ) -> list[UserPatientSummary]:
        effective_limit = max(1, min(limit, 200))
        with self.database.session() as session:
            statement = (
                select(Patient)
                .where(Patient.owner_user_id == owner_user_id)
                .order_by(Patient.full_name.asc(), Patient.external_id.asc())
            )
            if query:
                like = f"%{query.lower()}%"
                statement = statement.where(
                    func.lower(Patient.external_id).like(like)
                    | func.lower(func.coalesce(Patient.full_name, "")).like(like)
                )

            patients = session.scalars(statement.limit(effective_limit)).all()
            return [
                UserPatientSummary(
                    owner_user_id=row.owner_user_id,
                    owner_display_name=row.owner_display_name,
                    patient_external_id=row.external_id,
                    patient_name=row.full_name,
                    sex=Sex(row.sex) if row.sex else None,
                    birth_date=row.birth_date,
                )
                for row in patients
            ]

    def _build_reference_range_rows(
        self,
        reference_ranges: list[ReferenceRangeInput],
    ) -> list[IndicatorReferenceRange]:
        return [
            IndicatorReferenceRange(
                sex=item.sex.value if item.sex else None,
                min_age_days=_age_years_to_days(item.min_age_years),
                max_age_days=_age_years_to_days(item.max_age_years),
                lower_bound=_decimal_or_none(item.lower_bound),
                upper_bound=_decimal_or_none(item.upper_bound),
                note=item.note,
                priority=item.priority,
            )
            for item in reference_ranges
        ]

    def _indicator_entry_from_model(self, indicator: Indicator) -> IndicatorCatalogEntry:
        return IndicatorCatalogEntry(
            code=indicator.code,
            name=indicator.name,
            standard_system=indicator.standard_system,
            standard_code=indicator.standard_code,
            canonical_unit=indicator.canonical_unit,
            description=indicator.description,
            reference_range_count=len(indicator.reference_ranges),
            reference_ranges=[self._reference_range_view(item) for item in indicator.reference_ranges],
        )

    def _find_indicator_for_write(
        self,
        session,
        code: str,
        standard_system: str | None,
        standard_code: str | None,
    ) -> Indicator | None:
        by_standard = self._find_indicator_by_standard(session, standard_system, standard_code)
        by_code = self._find_indicator_by_code(session, code)
        if by_standard and by_code and by_standard.id != by_code.id:
            raise HealthMcpError(
                "indicator_code conflicts with an existing standard_system/standard_code mapping"
            )
        if by_standard and by_standard.code.lower() != code.lower():
            raise HealthMcpError(
                "The provided indicator_code does not match the existing indicator bound to this standard identity"
            )
        return by_standard or by_code

    def _find_indicator_for_import(
        self,
        session,
        code: str,
        standard_system: str | None,
        standard_code: str | None,
    ) -> Indicator | None:
        return self._find_indicator_by_standard(session, standard_system, standard_code) or self._find_indicator_by_code(
            session,
            code,
        )

    def _find_indicator_by_code(self, session, code: str) -> Indicator | None:
        return session.scalar(
            select(Indicator)
            .options(selectinload(Indicator.reference_ranges))
            .where(func.lower(Indicator.code) == code.lower())
        )

    def _find_indicator_by_standard(
        self,
        session,
        standard_system: str | None,
        standard_code: str | None,
    ) -> Indicator | None:
        if not standard_system or not standard_code:
            return None
        return session.scalar(
            select(Indicator)
            .options(selectinload(Indicator.reference_ranges))
            .where(
                func.lower(Indicator.standard_system) == standard_system.lower(),
                func.lower(Indicator.standard_code) == standard_code.lower(),
            )
        )

    def _apply_indicator_standard_identity(
        self,
        indicator: Indicator,
        standard_system: str,
        standard_code: str,
    ) -> None:
        if indicator.standard_system is None and indicator.standard_code is None:
            indicator.standard_system = standard_system
            indicator.standard_code = standard_code
            return
        if (
            indicator.standard_system
            and indicator.standard_system.lower() == standard_system.lower()
            and indicator.standard_code
            and indicator.standard_code.lower() == standard_code.lower()
        ):
            return
        raise HealthMcpError(
            f"Indicator '{indicator.code}' is already bound to "
            f"{indicator.standard_system}:{indicator.standard_code}"
        )

    def _reference_range_view(
        self,
        range_row: IndicatorReferenceRange,
    ) -> ReferenceRangeView:
        sex = Sex(range_row.sex) if range_row.sex else None
        return ReferenceRangeView(
            sex=sex,
            min_age_years=_days_to_years(range_row.min_age_days),
            max_age_years=_days_to_years(range_row.max_age_days),
            lower_bound=_float_or_none(range_row.lower_bound),
            upper_bound=_float_or_none(range_row.upper_bound),
            note=range_row.note,
            priority=range_row.priority,
        )

    def _reference_range_view_any(
        self,
        range_row: IndicatorReferenceRange | ComparableRange,
    ) -> ReferenceRangeView:
        if isinstance(range_row, IndicatorReferenceRange):
            return self._reference_range_view(range_row)
        sex = Sex(range_row.sex) if range_row.sex else None
        return ReferenceRangeView(
            sex=sex,
            min_age_years=_days_to_years(range_row.min_age_days),
            max_age_years=_days_to_years(range_row.max_age_days),
            lower_bound=_float_or_none(range_row.lower_bound),
            upper_bound=_float_or_none(range_row.upper_bound),
            note=range_row.note,
            priority=range_row.priority,
        )

    def _captured_range_from_bounds(
        self,
        lower_bound: float | None,
        upper_bound: float | None,
        reference_text: str | None,
    ) -> ComparableRange | None:
        lower_decimal = _decimal_or_none(lower_bound)
        upper_decimal = _decimal_or_none(upper_bound)
        if lower_decimal is None and upper_decimal is None:
            return None
        return ComparableRange(
            lower_bound=lower_decimal,
            upper_bound=upper_decimal,
            note=reference_text,
        )

    def _captured_range_from_result(self, result: LabResult) -> ComparableRange | None:
        if result.captured_lower_bound is None and result.captured_upper_bound is None:
            return None
        return ComparableRange(
            lower_bound=result.captured_lower_bound,
            upper_bound=result.captured_upper_bound,
            note=result.reference_text,
        )
