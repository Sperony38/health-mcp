from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.utcnow()


class Base(DeclarativeBase):
    pass


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "external_id", name="uq_patients_owner_external_id"),
        Index("ix_patients_owner_user_id", "owner_user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_user_id: Mapped[str] = mapped_column(String(128))
    owner_display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_id: Mapped[str] = mapped_column(String(128))
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sex: Mapped[str | None] = mapped_column(String(16), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    reports: Mapped[list["LabReport"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
    )


class Indicator(Base):
    __tablename__ = "indicators"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    canonical_unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    reference_ranges: Mapped[list["IndicatorReferenceRange"]] = relationship(
        back_populates="indicator",
        cascade="all, delete-orphan",
        order_by="IndicatorReferenceRange.priority.desc(), IndicatorReferenceRange.id.asc()",
    )
    results: Mapped[list["LabResult"]] = relationship(back_populates="indicator")


class IndicatorReferenceRange(Base):
    __tablename__ = "indicator_reference_ranges"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    indicator_id: Mapped[int] = mapped_column(ForeignKey("indicators.id", ondelete="CASCADE"), index=True)
    sex: Mapped[str | None] = mapped_column(String(16), nullable=True)
    min_age_days: Mapped[int | None] = mapped_column(nullable=True)
    max_age_days: Mapped[int | None] = mapped_column(nullable=True)
    lower_bound: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    upper_bound: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    priority: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    indicator: Mapped[Indicator] = relationship(back_populates="reference_ranges")


class LabReport(Base):
    __tablename__ = "lab_reports"
    __table_args__ = (
        UniqueConstraint(
            "patient_id",
            "source_system",
            "external_report_id",
            name="uq_lab_reports_patient_source_external",
        ),
        Index("ix_lab_reports_patient_collected_at", "patient_id", "collected_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"))
    source_system: Mapped[str | None] = mapped_column(String(128), nullable=True)
    external_report_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    patient: Mapped[Patient] = relationship(back_populates="reports")
    results: Mapped[list["LabResult"]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
    )


class LabResult(Base):
    __tablename__ = "lab_results"
    __table_args__ = (
        Index("ix_lab_results_report_indicator", "report_id", "indicator_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("lab_reports.id", ondelete="CASCADE"))
    indicator_id: Mapped[int] = mapped_column(ForeignKey("indicators.id", ondelete="RESTRICT"), index=True)
    measured_value: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    captured_lower_bound: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    captured_upper_bound: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    flag: Mapped[str | None] = mapped_column(String(32), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    report: Mapped[LabReport] = relationship(back_populates="results")
    indicator: Mapped[Indicator] = relationship(back_populates="results")
