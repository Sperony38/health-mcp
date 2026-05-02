import pytest

from datetime import date, datetime
from decimal import Decimal

from health_mcp.models import IndicatorReferenceRange
from health_mcp.schemas import IndicatorStatus, IndicatorUpsertInput, LabResultInput
from health_mcp.service import ComparableRange, classify_value, select_best_reference_range


def make_range(
    *,
    sex: str | None = None,
    min_age_days: int | None = None,
    max_age_days: int | None = None,
    lower: str | None = None,
    upper: str | None = None,
    priority: int = 0,
) -> IndicatorReferenceRange:
    return IndicatorReferenceRange(
        sex=sex,
        min_age_days=min_age_days,
        max_age_days=max_age_days,
        lower_bound=Decimal(lower) if lower is not None else None,
        upper_bound=Decimal(upper) if upper is not None else None,
        priority=priority,
    )


def test_sex_specific_range_beats_generic_range():
    generic = make_range(lower="3.5", upper="5.5")
    female = make_range(sex="female", lower="3.7", upper="5.1")

    matched = select_best_reference_range([generic, female], "female", 30 * 365)

    assert matched is female


def test_narrower_age_band_beats_open_ended_range():
    generic = make_range(lower="10", upper="20")
    child = make_range(min_age_days=0, max_age_days=18 * 365, lower="8", upper="15")

    matched = select_best_reference_range([generic, child], None, 10 * 365)

    assert matched is child


def test_classify_value_returns_expected_status():
    range_row = make_range(lower="4.0", upper="6.0")

    assert classify_value(Decimal("3.9"), range_row) == IndicatorStatus.low
    assert classify_value(Decimal("5.0"), range_row) == IndicatorStatus.normal
    assert classify_value(Decimal("6.1"), range_row) == IndicatorStatus.high


def test_classify_value_can_use_report_captured_range():
    captured_range = ComparableRange(
        lower_bound=Decimal("3.2"),
        upper_bound=Decimal("8.2"),
        note="3,2 - 8,2",
    )

    assert classify_value(Decimal("8.4"), captured_range) == IndicatorStatus.high


def test_lab_result_input_supports_agent_supplied_raw_fields():
    result = LabResultInput(
        indicator_code="lipoprotein-a",
        indicator_name="Ліпопротеїн (a)",
        standard_system="loinc",
        standard_code="43583-4",
        source_name="Ліпопротеїн (a), Lp(a), нефелометрія, кількісний",
        value=2.0,
        raw_value="<2*",
        value_operator="<",
        unit="мг/дл",
        captured_lower_bound=5.6,
        captured_upper_bound=33.8,
        reference_text="5,6 - 33,8",
        flag="lab_flagged",
    )

    assert result.source_name.startswith("Ліпопротеїн")
    assert result.raw_value == "<2*"
    assert result.value_operator == "<"
    assert result.reference_text == "5,6 - 33,8"


def test_standard_identity_fields_must_be_provided_together():
    with pytest.raises(ValueError):
        LabResultInput(
            indicator_code="cholesterol-total",
            indicator_name="Загальний холестерин",
            standard_system="loinc",
            value=5.3,
        )

    with pytest.raises(ValueError):
        IndicatorUpsertInput(
            code="cholesterol-total",
            name="Загальний холестерин",
            standard_code="2093-3",
        )
