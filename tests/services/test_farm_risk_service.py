"""农场确定性风险巡检服务测试。"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.exc import OperationalError

from app.exceptions import AppException
from app.schemas.weather import DailyForecastDetail, WeatherForecastResult
from app.services.farm_risk_service import (
    WeatherServiceProvider,
    inspect_field_work_quality,
    inspect_farm,
)
from app.services.farm_snapshot_service import FarmSnapshot
from app.tools.weather_risk import analyze_weather_risks


def _snapshot(
    *,
    field_area_mu: float = 10.0,
    work_area_mu: float = 9.0,
    depth_std: float = 2.0,
) -> FarmSnapshot:
    observed_at = datetime(2026, 7, 18, 8, 0, 0)
    return FarmSnapshot.model_validate(
        {
            "farm": {
                "id": 1,
                "user_id": 7,
                "name": "示范农场",
                "location": "山东寿光",
                "latitude": 36.8,
                "longitude": 118.7,
                "area_mu": field_area_mu,
                "description": "",
                "created_at": observed_at,
                "updated_at": observed_at,
            },
            "fields": [
                {
                    "id": 11,
                    "farm_id": 1,
                    "name": "A1",
                    "area_mu": field_area_mu,
                    "soil_type": "壤土",
                    "current_crop": "小麦",
                    "planting_date": None,
                    "expected_harvest": None,
                    "growth_stage": "拔节期",
                    "status": "planting",
                    "latitude": None,
                    "longitude": None,
                    "notes": "",
                    "boundary_json": "",
                    "created_at": observed_at,
                    "updated_at": observed_at,
                }
            ],
            "recent_trajectory_files": [
                {
                    "id": 101,
                    "field_id": 11,
                    "filename": "latest.xlsx",
                    "work_area_mu": work_area_mu,
                    "depth_std": depth_std,
                    "created_at": observed_at,
                }
            ],
            "pending_task_count": 0,
            "captured_at": observed_at,
            "data_gaps": [],
        }
    )


class StaticWeatherProvider:
    def __init__(self, precipitation_mm: float, *, source: str = "test") -> None:
        self.precipitation_mm = precipitation_mm
        self.source = source
        self.calls: list[tuple[str, int]] = []

    async def get_forecast_with_alerts(
        self,
        location: str,
        days: int = 2,
    ) -> WeatherForecastResult:
        self.calls.append((location, days))
        return WeatherForecastResult(
            location=location,
            daily=[
                DailyForecastDetail(
                    date="2026-07-19",
                    min_temp=22,
                    max_temp=29,
                    precipitation_mm=self.precipitation_mm,
                    condition="暴雨",
                )
            ],
            source=self.source,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("precipitation_mm", "expected_severity"),
    [
        (49.9, None),
        (50.0, "high"),
        (79.9, "high"),
        (80.0, "critical"),
    ],
)
async def test_inspect_farm_applies_thresholds_to_first_calendar_day_proxy(
    precipitation_mm: float,
    expected_severity: str | None,
) -> None:
    provider = StaticWeatherProvider(precipitation_mm)

    result = await inspect_farm(_snapshot(), weather_provider=provider)

    weather_risks = [risk for risk in result.risks if risk.risk_key == "weather.rainstorm_drainage"]
    assert provider.calls == [("山东寿光", 2)]
    if expected_severity is None:
        assert weather_risks == []
    else:
        assert len(weather_risks) == 1
        risk = weather_risks[0]
        assert risk.severity == expected_severity
        assert risk.confidence == 0.75
        assert risk.evidence
        assert risk.suggested_actions
        evidence = risk.evidence[0]
        assert "首个预报日" in evidence.summary
        assert "未来 24 小时" not in evidence.summary
        assert evidence.payload["forecast_basis"] == "first_calendar_day_proxy"
        assert evidence.payload["precipitation_first_forecast_day_mm"] == precipitation_mm
        assert "precipitation_24h_mm" not in evidence.payload


@pytest.mark.asyncio
async def test_inspect_farm_forwards_requested_forecast_days() -> None:
    provider = StaticWeatherProvider(0)

    await inspect_farm(_snapshot(), weather_provider=provider, days=7)

    assert provider.calls == [("山东寿光", 7)]


def test_inspect_field_work_quality_is_deterministic_and_field_scoped() -> None:
    result = inspect_field_work_quality(_snapshot(depth_std=5.1), field_id=11, limit=5)

    assert len(result.risks) == 1
    assert result.risks[0].risk_key.startswith("trajectory.work_quality:11:")
    assert result.degraded is False
    assert result.warnings == []

    other_field = inspect_field_work_quality(
        _snapshot(depth_std=5.1),
        field_id=999,
        limit=5,
    )
    assert other_field.risks == []


@pytest.mark.asyncio
async def test_mock_forecast_is_degraded_and_never_emits_weather_risk() -> None:
    result = await inspect_farm(
        _snapshot(),
        weather_provider=StaticWeatherProvider(100.0, source="mock"),
    )

    assert result.degraded is True
    assert "weather_forecast_mock_fallback" in result.data_gaps
    assert any("mock" in warning.lower() for warning in result.warnings)
    assert not any(risk.risk_key.startswith("weather.") for risk in result.risks)
    assert not any(
        evidence.source_type == "weather_forecast" and risk.confidence >= 0.8
        for risk in result.risks
        for evidence in risk.evidence
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("work_area_mu", "depth_std", "expected_reasons"),
    [
        (9.0, 5.1, {"depth_variability"}),
        (7.9, 2.0, {"insufficient_coverage"}),
        (7.0, 6.0, {"depth_variability", "insufficient_coverage"}),
    ],
)
async def test_inspect_farm_emits_structured_trajectory_quality_evidence(
    work_area_mu: float,
    depth_std: float,
    expected_reasons: set[str],
) -> None:
    result = await inspect_farm(
        _snapshot(work_area_mu=work_area_mu, depth_std=depth_std),
        weather_provider=StaticWeatherProvider(0),
    )

    risk = next(item for item in result.risks if item.risk_key.startswith("trajectory.work_quality"))
    assert risk.severity == "medium"
    assert 0.0 <= risk.confidence <= 1.0
    assert risk.evidence
    assert risk.suggested_actions
    assert set(risk.evidence[0].payload["triggered_rules"]) == expected_reasons


@pytest.mark.asyncio
async def test_trajectory_quality_exact_boundaries_do_not_trigger() -> None:
    result = await inspect_farm(
        _snapshot(work_area_mu=8.0, depth_std=5.0),
        weather_provider=StaticWeatherProvider(0),
    )

    assert not any(
        risk.risk_key.startswith("trajectory.work_quality")
        for risk in result.risks
    )


class FailingWeatherProvider:
    async def get_forecast_with_alerts(
        self,
        location: str,
        days: int = 2,
    ) -> WeatherForecastResult:
        raise RuntimeError("weather backend unavailable")


class ApplicationErrorWeatherProvider:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    async def get_forecast_with_alerts(
        self,
        location: str,
        days: int = 2,
    ) -> WeatherForecastResult:
        raise AppException(
            message="provider error",
            status_code=self.status_code,
        )


@pytest.mark.asyncio
async def test_inspect_farm_degrades_without_high_confidence_weather_risk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    warnings: list[str] = []
    monkeypatch.setattr(
        "app.services.farm_risk_service.logger.warning",
        lambda message, *args: warnings.append(message.format(*args)),
    )

    result = await inspect_farm(_snapshot(depth_std=6.0), weather_provider=FailingWeatherProvider())

    assert result.degraded is True
    assert "weather_forecast_unavailable" in result.data_gaps
    assert warnings
    assert not any(
        risk.risk_key.startswith("weather.") and risk.confidence >= 0.8
        for risk in result.risks
    )
    assert any(risk.risk_key.startswith("trajectory.") for risk in result.risks)


@pytest.mark.asyncio
async def test_weather_provider_service_failure_becomes_data_gap() -> None:
    result = await inspect_farm(
        _snapshot(),
        weather_provider=ApplicationErrorWeatherProvider(503),
    )

    assert result.degraded is True
    assert "weather_forecast_unavailable" in result.data_gaps


@pytest.mark.asyncio
async def test_ownership_and_database_errors_from_provider_propagate() -> None:
    with pytest.raises(AppException) as forbidden:
        await inspect_farm(
            _snapshot(),
            weather_provider=ApplicationErrorWeatherProvider(403),
        )
    assert forbidden.value.status_code == 403

    class DatabaseErrorProvider:
        async def get_forecast_with_alerts(
            self,
            location: str,
            days: int = 2,
        ) -> WeatherForecastResult:
            raise OperationalError("forecast query", {}, RuntimeError("db down"))

    with pytest.raises(OperationalError):
        await inspect_farm(_snapshot(), weather_provider=DatabaseErrorProvider())


@pytest.mark.asyncio
async def test_weather_service_provider_calls_existing_service_with_two_days(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backing_provider = StaticWeatherProvider(0)
    monkeypatch.setattr(
        "app.services.farm_risk_service.weather_service.get_weather_service",
        lambda: backing_provider,
    )

    await WeatherServiceProvider().get_forecast_with_alerts("山东寿光")

    assert backing_provider.calls == [("山东寿光", 2)]


def test_existing_daily_weather_alert_thresholds_are_preserved() -> None:
    alerts = analyze_weather_risks(
        [
            DailyForecastDetail(
                date="2026-07-19",
                min_temp=20,
                max_temp=30,
                precipitation_mm=99.9,
            ),
            DailyForecastDetail(
                date="2026-07-20",
                min_temp=20,
                max_temp=30,
                precipitation_mm=100.0,
            ),
        ]
    )

    assert [alert.severity for alert in alerts] == ["中", "高"]
