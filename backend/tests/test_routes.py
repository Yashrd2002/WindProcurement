from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_overview_endpoint_default() -> None:
    response = client.get("/api/v1/overview")
    assert response.status_code == 200
    data = response.json()
    assert data["target_month"] == "2026-01"
    assert data["cutoff_time"] == "12:00"
    assert "cards" in data
    assert data["total_expected_intervals"] == 1488


def test_overview_endpoint_custom_params() -> None:
    response = client.get("/api/v1/overview?month=2026-01&cutoff=17:00")
    assert response.status_code == 200
    data = response.json()
    assert data["cutoff_time"] == "17:00"


def test_overview_endpoint_invalid_month() -> None:
    response = client.get("/api/v1/overview?month=invalid-date")
    assert response.status_code == 422
    assert "Invalid month format" in response.text


def test_overview_endpoint_invalid_cutoff() -> None:
    response = client.get("/api/v1/overview?cutoff=25:00")
    assert response.status_code == 422
    assert "Invalid cutoff time format" in response.text


def test_timeseries_endpoint() -> None:
    response = client.get("/api/v1/timeseries")
    assert response.status_code == 200
    data = response.json()
    assert "points" in data
    assert data["target_month"] == "2026-01"


def test_intervals_endpoint_pagination() -> None:
    response = client.get("/api/v1/intervals?page=1&page_size=24")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["page_size"] == 24
    assert "items" in data


def test_intervals_endpoint_invalid_pagination() -> None:
    # page must be >= 1
    response = client.get("/api/v1/intervals?page=0")
    assert response.status_code == 422

    # page_size must be <= 200
    response = client.get("/api/v1/intervals?page_size=500")
    assert response.status_code == 422


def test_quality_endpoint() -> None:
    response = client.get("/api/v1/quality")
    assert response.status_code == 200
    data = response.json()
    assert data["overall_status"] == "complete"
    assert "audits" in data
    assert data["expected_intervals"] == 1488
