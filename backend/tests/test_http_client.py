import pytest
from app.core.config import Settings
from app.core.http_client import create_http_client


def test_http_client_configuration() -> None:
    settings = Settings(
        elexon_base_url="https://data.elexon.co.uk/bmrs/api/v1",
        http_timeout_seconds=12.0,
        http_connect_timeout_seconds=4.0,
        http_max_connections=30,
        http_max_keepalive=10,
    )
    client = create_http_client(settings)

    assert str(client.base_url).rstrip("/") == "https://data.elexon.co.uk/bmrs/api/v1"
    assert client.timeout.read == 12.0
    assert client.timeout.connect == 4.0
    assert "Wind Procurement Intelligence" in client.headers["user-agent"]
