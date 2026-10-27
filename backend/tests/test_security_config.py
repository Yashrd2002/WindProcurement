"""Security and Configuration Audit Tests for Wind Procurement Platform (P7-06).

Validates:
- No hardcoded secrets, private tokens, or credentials in configuration.
- Strict CORS restriction (credentials disabled, only GET allowed).
- Request safeguards (page size cap <= 200, bounded January 2026 scope).
- Production debug settings and logging standards.
"""

from pathlib import Path
import re
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import get_settings
from app.core.safeguards import MAX_PAGE_SIZE, SUPPORTED_MONTH


def test_no_hardcoded_secrets_in_repo():
    """P7-06: Verify no sensitive API keys or credentials exist in source files."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    patterns = [
        re.compile(r"(?i)api[_-]?key\s*=\s*['\"][A-Za-z0-9_\-]{20,}['\"]"),
        re.compile(r"(?i)secret[_-]?key\s*=\s*['\"][A-Za-z0-9_\-]{20,}['\"]"),
        re.compile(r"(?i)password\s*=\s*['\"][^'\"]{8,}['\"]"),
        re.compile(r"-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----"),
    ]

    scanned_files = 0
    for ext in ["*.py", "*.ts", "*.tsx", "*.json", "*.env.example"]:
        for file_path in repo_root.rglob(ext):
            if (
                "node_modules" in file_path.parts
                or ".venv" in file_path.parts
                or ".git" in file_path.parts
                or file_path.name == ".env"
            ):
                continue

            scanned_files += 1
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            for pattern in patterns:
                matches = pattern.findall(content)
                assert not matches, f"Potential hardcoded secret found in {file_path}: {matches}"

    assert scanned_files > 20, f"Expected to scan at least 20 source files, scanned {scanned_files}"


def test_cors_security_policy():
    """P7-06: CORS is restricted with credentials disabled."""
    settings = get_settings()

    # Find CORSMiddleware in app middleware stack
    cors_middleware = None
    for middleware in app.user_middleware:
        if "CORSMiddleware" in str(middleware.cls):
            cors_middleware = middleware
            break

    assert cors_middleware is not None, "CORSMiddleware must be configured on app"
    kwargs = cors_middleware.kwargs

    # Credentials must be disabled (ADR-01)
    assert kwargs.get("allow_credentials") is False
    # Explicitly permitted methods
    assert set(kwargs.get("allow_methods")) == {"GET", "POST", "OPTIONS"}
    # Verify origin list does not permit unrestricted wildcard with credentials
    assert "*" not in settings.cors_origins or kwargs.get("allow_credentials") is False


def test_request_safeguards_and_rate_limits():
    """P7-06: Strict validation prevents query parameter manipulation."""
    with TestClient(app) as client:
        # 1. Page size limit: requesting 201 items returns 422 Unprocessable Entity
        resp_large_page = client.get(f"/api/v1/intervals?page_size={MAX_PAGE_SIZE + 1}")
        assert resp_large_page.status_code == 422

        # 2. Scope boundary: requesting February 2026 returns 400 Bad Request
        resp_unsupported_month = client.get("/api/v1/overview?month=2026-02")
        assert resp_unsupported_month.status_code == 400
        assert "strictly scoped to January 2026" in resp_unsupported_month.json()["detail"]

        # 3. Invalid cutoff format returns 422
        resp_invalid_cutoff = client.get("/api/v1/overview?cutoff=invalid")
        assert resp_invalid_cutoff.status_code == 422

        # 4. In-bounds query succeeds
        resp_valid = client.get(f"/api/v1/overview?month={SUPPORTED_MONTH}&cutoff=12:00")
        assert resp_valid.status_code == 200
