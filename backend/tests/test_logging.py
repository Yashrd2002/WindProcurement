from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_request_id_generated_when_missing() -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) > 10


def test_request_id_preserved_when_supplied() -> None:
    custom_id = "custom-trace-id-12345"
    response = client.get("/health/live", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("x-request-id") == custom_id
