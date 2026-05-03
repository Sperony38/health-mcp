from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Sex(str, Enum):
    male = "male"
    female = "female"
    other = "other"
    unknown = "unknown"


class IndicatorStatus(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"
    unknown = "unknown"


class ReferenceRangeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    sex: Sex | None = Field(default=None, description="Sex-specific range. Null means any sex.")
    min_age_years: float | None = Field(default=None, ge=0)
    max_age_years: float | None = Field(default=None, ge=0)
    lower_bound: float | None = None
    upper_bound: float | None = None
    note: str | None = None
    priority: int = 0

    @model_validator(mode="after")
    def validate_bounds(self) -> "ReferenceRangeInput":
        if self.min_age_years is not None and self.max_age_years is not None:
            if self.max_age_years < self.min_age_years:
                raise ValueError("max_age_years must be greater than or equal to min_age_years")
        if self.lower_bound is None and self.upper_bound is None:
            raise ValueError("At least one of lower_bound or upper_bound must be set")
        return self


class ReferenceRangeView(BaseModel):
    sex: Sex | None = None
    min_age_years: float | None = None
    max_age_years: float | None = None
    lower_bound: float | None = None
    upper_bound: float | None = None
    note: str | None = None
    priority: int = 0


class IndicatorUpsertInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    code: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    standard_system: str | None = Field(default=None, max_length=32)
    standard_code: str | None = Field(default=None, max_length=64)
    canonical_unit: str | None = Field(default=None, max_length=64)
    description: str | None = None
    reference_ranges: list[ReferenceRangeInput] = Field(default_factory=list)
    replace_reference_ranges: bool = True

    @model_validator(mode="after")
    def validate_standard_identity(self) -> "IndicatorUpsertInput":
        if (self.standard_system is None) != (self.standard_code is None):
            raise ValueError("standard_system and standard_code must be provided together")
        return self


class IndicatorSummary(BaseModel):
    code: str
    name: str
    standard_system: str | None = None
    standard_code: str | None = None
    canonical_unit: str | None = None
    reference_range_count: int


class IndicatorCatalogEntry(IndicatorSummary):
    description: str | None = None
    reference_ranges: list[ReferenceRangeView] = Field(default_factory=list)


class LabResultInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    indicator_code: str = Field(min_length=1, max_length=128)
    indicator_name: str | None = Field(default=None, max_length=255)
    standard_system: str | None = Field(default=None, max_length=32)
    standard_code: str | None = Field(default=None, max_length=64)
    source_name: str | None = Field(default=None, max_length=255)
    value: float
    raw_value: str | None = Field(default=None, max_length=64)
    value_operator: str | None = Field(default=None, max_length=8)
    unit: str | None = Field(default=None, max_length=64)
    captured_lower_bound: float | None = None
    captured_upper_bound: float | None = None
    reference_text: str | None = None
    flag: str | None = Field(default=None, max_length=32)
    comment: str | None = None

    @model_validator(mode="after")
    def validate_standard_identity(self) -> "LabResultInput":
        if (self.standard_system is None) != (self.standard_code is None):
            raise ValueError("standard_system and standard_code must be provided together")
        return self


class LabReportInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    owner_user_id: str = Field(min_length=1, max_length=128)
    owner_display_name: str | None = Field(default=None, max_length=255)
    patient_external_id: str = Field(min_length=1, max_length=128)
    patient_name: str | None = Field(default=None, max_length=255)
    patient_birth_date: date | None = None
    patient_sex: Sex | None = None
    collected_at: datetime
    source_system: str = Field(default="manual", max_length=128)
    external_report_id: str | None = Field(default=None, max_length=128)
    notes: str | None = None
    results: list[LabResultInput] = Field(min_length=1)


class ImportedLabResult(BaseModel):
    indicator_code: str
    indicator_name: str
    standard_system: str | None = None
    standard_code: str | None = None
    source_name: str | None = None
    value: float
    raw_value: str | None = None
    unit: str | None = None
    status: IndicatorStatus
    reference_range: ReferenceRangeView | None = None
    reference_text: str | None = None
    warnings: list[str] = Field(default_factory=list)


class ImportLabReportResult(BaseModel):
    report_id: int
    owner_user_id: str
    patient_external_id: str
    source_system: str
    collected_at: datetime
    imported_count: int
    results: list[ImportedLabResult]


class IndicatorHistoryPoint(BaseModel):
    report_id: int
    collected_at: datetime
    source_system: str | None = None
    external_report_id: str | None = None
    standard_system: str | None = None
    standard_code: str | None = None
    source_name: str | None = None
    value: float
    raw_value: str | None = None
    unit: str | None = None
    status: IndicatorStatus
    reference_range: ReferenceRangeView | None = None
    reference_text: str | None = None


class IndicatorHistoryView(BaseModel):
    owner_user_id: str
    patient_external_id: str
    patient_name: str | None = None
    indicator_code: str
    indicator_name: str
    standard_system: str | None = None
    standard_code: str | None = None
    canonical_unit: str | None = None
    points: list[IndicatorHistoryPoint] = Field(default_factory=list)


class PatientIndicatorBatchView(BaseModel):
    owner_user_id: str
    patient_external_id: str
    patient_name: str | None = None
    indicators: list[IndicatorHistoryView] = Field(default_factory=list)
    missing_indicator_codes: list[str] = Field(default_factory=list)


class UserPatientSummary(BaseModel):
    owner_user_id: str
    owner_display_name: str | None = None
    patient_external_id: str
    patient_name: str | None = None
    sex: Sex | None = None
    birth_date: date | None = None


class ServiceUserSummary(BaseModel):
    owner_user_id: str
    owner_display_name: str | None = None
    patient_count: int = 0
    report_count: int = 0
    last_report_at: datetime | None = None
