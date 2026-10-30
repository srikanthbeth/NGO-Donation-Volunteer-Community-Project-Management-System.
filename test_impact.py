
import os
from uuid import uuid4
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv(".env")

os.environ["ENVIRONMENT"] = "development"
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:Srik8499@localhost:5433/ngo_management_test",
)

from fastapi.testclient import TestClient
import pytest

from db.base import Base
from db.session import SessionLocal
from main import app
from models.user import User


client = TestClient(app)
PASSWORD = "TestPassword123!"


@pytest.fixture(autouse=True)
def clean_database():
    db = SessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
    finally:
        db.close()

    yield

    db = SessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
    finally:
        db.close()


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def create_user(role="NGO_MANAGER"):
    email = f"impact_{uuid4().hex[:10]}@example.com"

    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Impact Test User",
            "email": email,
            "password": PASSWORD,
        },
    )
    assert response.status_code in (200, 201), response.text

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        user.role = role
        db.commit()
    finally:
        db.close()

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert login_response.status_code == 200, login_response.text

    return auth_headers(login_response.json()["access_token"])


def create_project(headers):
    response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "title": f"Impact Project {uuid4().hex[:8]}",
            "description": "Project used for impact tracking tests",
            "location": "Hyderabad",
            "start_date": "2026-01-01T00:00:00",
            "end_date": "2026-12-31T00:00:00",
            "budget": "100000.00",
            "currency": "INR",
            "status": "ACTIVE",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def submit_update(headers, project_id, payload=None):
    if payload is None:
        payload = {
            "beneficiaries_served": 25,
            "volunteer_hours": "12.50",
            "resources_distributed": 40,
            "projects_completed": 1,
            "funds_utilized": "2500.00",
            "milestones_achieved": 3,
            "notes": "Monthly impact report",
        }

    return client.post(
        f"/api/v1/impact/projects/{project_id}/updates",
        headers=headers,
        json=payload,
    )


def test_manager_can_submit_impact_update():
    headers = create_user("NGO_MANAGER")
    project = create_project(headers)

    response = submit_update(headers, project["id"])

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["project_id"] == project["id"]
    assert data["beneficiaries_served"] == 25
    assert data["volunteer_hours"] == "12.50"
    assert data["resources_distributed"] == 40
    assert data["projects_completed"] == 1
    assert data["funds_utilized"] == "2500.00"
    assert data["milestones_achieved"] == 3
    assert data["notes"] == "Monthly impact report"
    assert data["submitted_by"] > 0
    assert "created_at" in data


def test_super_admin_can_submit_impact_update():
    headers = create_user("SUPER_ADMIN")
    project = create_project(headers)

    response = submit_update(headers, project["id"])

    assert response.status_code == 201, response.text


def test_donor_cannot_submit_impact_update():
    manager_headers = create_user("NGO_MANAGER")
    project = create_project(manager_headers)
    donor_headers = create_user("DONOR")

    response = submit_update(donor_headers, project["id"])

    assert response.status_code == 403


def test_volunteer_cannot_submit_impact_update():
    manager_headers = create_user("NGO_MANAGER")
    project = create_project(manager_headers)
    volunteer_headers = create_user("VOLUNTEER")

    response = submit_update(volunteer_headers, project["id"])

    assert response.status_code == 403


def test_unauthenticated_user_cannot_submit_impact_update():
    response = client.post(
        "/api/v1/impact/projects/1/updates",
        json={"beneficiaries_served": 10},
    )

    assert response.status_code == 401


def test_submit_update_for_missing_project_returns_404():
    headers = create_user("NGO_MANAGER")

    response = submit_update(headers, 999999)

    assert response.status_code == 404


@pytest.mark.parametrize(
    "field,value",
    [
        ("beneficiaries_served", -1),
        ("volunteer_hours", "-1.00"),
        ("resources_distributed", -1),
        ("projects_completed", -1),
        ("funds_utilized", "-10.00"),
        ("milestones_achieved", -1),
    ],
)
def test_negative_impact_metrics_are_rejected(field, value):
    headers = create_user("NGO_MANAGER")
    project = create_project(headers)
    payload = {"beneficiaries_served": 1, field: value}

    response = submit_update(headers, project["id"], payload)

    assert response.status_code == 422, response.text


def test_impact_metrics_default_to_zero():
    headers = create_user("NGO_MANAGER")
    project = create_project(headers)

    response = submit_update(headers, project["id"], {})

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["beneficiaries_served"] == 0
    assert data["volunteer_hours"] == "0.00"
    assert data["resources_distributed"] == 0
    assert data["projects_completed"] == 0
    assert data["funds_utilized"] == "0.00"
    assert data["milestones_achieved"] == 0


def test_impact_history_preserves_multiple_updates():
    headers = create_user("NGO_MANAGER")
    project = create_project(headers)

    first = submit_update(
        headers,
        project["id"],
        {"beneficiaries_served": 10, "notes": "First report"},
    )
    second = submit_update(
        headers,
        project["id"],
        {"beneficiaries_served": 20, "notes": "Second report"},
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] != second.json()["id"]

    response = client.get(
        f"/api/v1/impact/projects/{project['id']}/history",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert {item["notes"] for item in data["items"]} == {
        "First report",
        "Second report",
    }


def test_impact_summary_aggregates_all_updates():
    headers = create_user("NGO_MANAGER")
    project = create_project(headers)

    first = submit_update(
        headers,
        project["id"],
        {
            "beneficiaries_served": 10,
            "volunteer_hours": "2.50",
            "resources_distributed": 5,
            "projects_completed": 1,
            "funds_utilized": "1000.00",
            "milestones_achieved": 2,
        },
    )
    second = submit_update(
        headers,
        project["id"],
        {
            "beneficiaries_served": 20,
            "volunteer_hours": "3.50",
            "resources_distributed": 8,
            "projects_completed": 1,
            "funds_utilized": "1500.00",
            "milestones_achieved": 3,
        },
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text

    response = client.get(
        f"/api/v1/impact/projects/{project['id']}/summary",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["update_count"] == 2
    assert data["beneficiaries_served"] == 30
    assert data["volunteer_hours"] == "6.00"
    assert data["resources_distributed"] == 13
    assert data["projects_completed"] == 2
    assert data["funds_utilized"] == "2500.00"
    assert data["milestones_achieved"] == 5


def test_summary_for_project_without_updates_returns_zero_metrics():
    headers = create_user("NGO_MANAGER")
    project = create_project(headers)

    response = client.get(
        f"/api/v1/impact/projects/{project['id']}/summary",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["update_count"] == 0
    assert data["beneficiaries_served"] == 0
    assert data["volunteer_hours"] == "0.00"
    assert data["resources_distributed"] == 0
    assert data["projects_completed"] == 0
    assert data["funds_utilized"] == "0.00"
    assert data["milestones_achieved"] == 0


def test_history_supports_pagination():
    headers = create_user("NGO_MANAGER")
    project = create_project(headers)

    for count in range(3):
        response = submit_update(
            headers,
            project["id"],
            {"beneficiaries_served": count + 1},
        )
        assert response.status_code == 201, response.text

    response = client.get(
        f"/api/v1/impact/projects/{project['id']}/history",
        headers=headers,
        params={"page": 1, "page_size": 2},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 2


def test_donor_cannot_view_impact_history():
    manager_headers = create_user("NGO_MANAGER")
    project = create_project(manager_headers)
    donor_headers = create_user("DONOR")

    response = client.get(
        f"/api/v1/impact/projects/{project['id']}/history",
        headers=donor_headers,
    )

    assert response.status_code == 403


def test_history_for_missing_project_returns_404():
    headers = create_user("NGO_MANAGER")

    response = client.get(
        "/api/v1/impact/projects/999999/history",
        headers=headers,
    )

    assert response.status_code == 404
