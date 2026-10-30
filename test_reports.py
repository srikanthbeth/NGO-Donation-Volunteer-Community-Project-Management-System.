import os
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv()

os.environ["ENVIRONMENT"] = "development"
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:Srik8499@localhost:5433/ngo_management_system_test",
)

from fastapi.testclient import TestClient

from main import app


client = TestClient(app)

BASE_URL = "/api/v1/reports"

REPORT_ENDPOINTS = [
    "/donations",
    "/campaigns",
    "/volunteers",
    "/projects",
    "/expenses",
    "/resources",
    "/beneficiaries",
]


def unique_email():
    return f"report_test_{uuid4().hex[:10]}@example.com"


def register_user():
    """Register a donor and return authorization headers."""
    email = unique_email()
    password = "TestPassword@123"

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Report Test User",
            "email": email,
            "password": password,
        },
    )

    assert register_response.status_code == 201, (
        f"Registration failed: {register_response.status_code} "
        f"{register_response.text}"
    )

    assert register_response.json()["role"] == "DONOR"

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )

    assert login_response.status_code == 200, (
        f"Login failed: {login_response.status_code} "
        f"{login_response.text}"
    )

    token = login_response.json().get("access_token")
    assert token, f"Access token missing: {login_response.text}"

    return {"Authorization": f"Bearer {token}"}


def test_reports_require_authentication():
    for endpoint in REPORT_ENDPOINTS:
        response = client.get(BASE_URL + endpoint)

        assert response.status_code in (401, 403), (
            f"{endpoint}: expected authentication failure, "
            f"received {response.status_code}: {response.text}"
        )


def test_donor_report_access_is_checked():
    headers = register_user()

    response = client.get(
        f"{BASE_URL}/donations",
        headers=headers,
    )

    # A donor should not have access to finance management reports.
    assert response.status_code == 403, response.text


def test_donor_cannot_access_campaign_management_report():
    headers = register_user()

    response = client.get(
        f"{BASE_URL}/campaigns",
        headers=headers,
    )

    assert response.status_code == 403, response.text


def test_donor_cannot_access_volunteer_report():
    headers = register_user()

    response = client.get(
        f"{BASE_URL}/volunteers",
        headers=headers,
    )

    assert response.status_code == 403, response.text


def test_donor_cannot_access_project_report():
    headers = register_user()

    response = client.get(
        f"{BASE_URL}/projects",
        headers=headers,
    )

    assert response.status_code == 403, response.text


def test_donor_cannot_access_expense_report():
    headers = register_user()

    response = client.get(
        f"{BASE_URL}/expenses",
        headers=headers,
    )

    assert response.status_code == 403, response.text


def test_donor_cannot_access_resource_report():
    headers = register_user()

    response = client.get(
        f"{BASE_URL}/resources",
        headers=headers,
    )

    assert response.status_code == 403, response.text


def test_donor_cannot_access_beneficiary_report():
    headers = register_user()

    response = client.get(
        f"{BASE_URL}/beneficiaries",
        headers=headers,
    )

    assert response.status_code == 403, response.text


def test_donor_cannot_export_donation_report():
    headers = register_user()

    response = client.get(
        f"{BASE_URL}/donations/export",
        headers=headers,
    )

    assert response.status_code == 403, response.text


def test_unknown_report_returns_not_found():
    headers = register_user()

    response = client.get(
        f"{BASE_URL}/unknown-report",
        headers=headers,
    )

    assert response.status_code == 404, response.text
