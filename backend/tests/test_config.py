import pytest

from app.config import Settings


def test_cors_origins_defaults_to_the_local_frontend() -> None:
    assert Settings().cors_origins == ["http://localhost:5173"]


def test_cors_origins_reads_a_single_origin_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://caselaw.example.com")

    assert Settings().cors_origins == ["https://caselaw.example.com"]


def test_cors_origins_reads_a_comma_separated_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "CORS_ORIGINS", "http://localhost:5173, https://caselaw.example.com"
    )

    assert Settings().cors_origins == [
        "http://localhost:5173",
        "https://caselaw.example.com",
    ]


def test_environment_is_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")

    assert Settings().environment == "production"


def test_export_limit_defaults_to_the_measured_ceiling() -> None:
    assert Settings().export_max_decisions == 1000


def test_export_limit_can_be_lowered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXPORT_MAX_DECISIONS", "250")
    assert Settings().export_max_decisions == 250


@pytest.mark.parametrize("value", ["0", "-1", "1001"])
def test_export_limit_cannot_be_empty_or_exceed_the_measured_ceiling(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    from pydantic import ValidationError

    monkeypatch.setenv("EXPORT_MAX_DECISIONS", value)
    with pytest.raises(ValidationError):
        Settings()
