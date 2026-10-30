
import os
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import delete

load_dotenv()

os.environ["ENVIRONMENT"] = "development"
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:Srik8499@localhost:5433/ngo_management_system_test",
)

# Import main first so all application models are registered.
from main import app
from db.base import Base
from db.session import SessionLocal
from models.user import User

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_database():
    with SessionLocal() as db:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(delete(table))
        db.commit()

    yield

    with SessionLocal() as db:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(delete(table))
        db.commit()


def create_user(role="NGO_MANAGER"):
    email = f"{role.lower()}_{uuid4().hex[:10]}@example.com"
    password = "TestPassword123!"

    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": f"Test {role}",
            "email": email,
            "password": password,
        },
    )
    assert response.status_code in (200, 201), response.text

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        user.role = role
        db.commit()

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200, login_response.text

    token = login_response.json()["access_token"]
    return {
        "email": email,
        "headers": {"Authorization": f"Bearer {token}"},
        "role": role,
    }


def create_project(headers):
    response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "title": f"Milestone Project {uuid4().hex[:6]}",
            "description": "Project created for milestone testing",
            "start_date": "2026-10-01",
            "status": "ACTIVE",
            "budget": 10000,
            "currency": "INR",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_milestone(headers, project_id, **overrides):
    payload = {
        "project_id": project_id,
        "title": f"Milestone {uuid4().hex[:6]}",
        "description": "Milestone test description",
        "due_date": "2026-12-01T00:00:00Z",
        "status": "PENDING",
    }
    payload.update(overrides)

    return client.post(
        "/api/v1/milestones",
        headers=headers,
        json=payload,
    )


def test_create_milestone_success():
    manager = create_user()
    project = create_project(manager["headers"])

    response = create_milestone(manager["headers"], project["id"])

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["project_id"] == project["id"]
    assert data["status"] == "PENDING"
    assert data["title"].startswith("Milestone")


def test_create_milestone_requires_authentication():
    response = client.post(
        "/api/v1/milestones",
        json={"project_id": 1, "title": "Unauthenticated milestone"},
    )
    assert response.status_code in (401, 403)


def test_create_milestone_forbidden_for_donor():
    donor = create_user("DONOR")
    response = create_milestone(donor["headers"], 1)
    assert response.status_code == 403


def test_create_milestone_rejects_missing_project():
    manager = create_user()

    response = create_milestone(
        manager["headers"],
        999999,
        title="Invalid project milestone",
    )

    assert response.status_code == 404


def test_create_milestone_rejects_blank_title():
    manager = create_user()
    project = create_project(manager["headers"])

    response = create_milestone(
        manager["headers"],
        project["id"],
        title="   ",
    )

    assert response.status_code == 422


def test_list_milestones():
    manager = create_user()
    project = create_project(manager["headers"])

    first = create_milestone(manager["headers"], project["id"])
    second = create_milestone(manager["headers"], project["id"])
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text

    response = client.get(
        "/api/v1/milestones",
        headers=manager["headers"],
        params={"project_id": project["id"]},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_milestones_supports_pagination():
    manager = create_user()
    project = create_project(manager["headers"])

    for _ in range(3):
        response = create_milestone(manager["headers"], project["id"])
        assert response.status_code == 201, response.text

    response = client.get(
        "/api/v1/milestones",
        headers=manager["headers"],
        params={"project_id": project["id"], "page": 1, "page_size": 2},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 2


def test_get_milestone_by_id():
    manager = create_user()
    project = create_project(manager["headers"])
    created = create_milestone(manager["headers"], project["id"])
    assert created.status_code == 201, created.text

    milestone_id = created.json()["id"]
    response = client.get(
        f"/api/v1/milestones/{milestone_id}",
        headers=manager["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == milestone_id


def test_get_missing_milestone_returns_404():
    manager = create_user()

    response = client.get(
        "/api/v1/milestones/999999",
        headers=manager["headers"],
    )

    assert response.status_code == 404


def test_update_milestone():
    manager = create_user()
    project = create_project(manager["headers"])
    created = create_milestone(manager["headers"], project["id"])
    assert created.status_code == 201, created.text

    milestone_id = created.json()["id"]
    response = client.patch(
        f"/api/v1/milestones/{milestone_id}",
        headers=manager["headers"],
        json={
            "title": "Updated milestone title",
            "status": "IN_PROGRESS",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["title"] == "Updated milestone title"
    assert response.json()["status"] == "IN_PROGRESS"


def test_update_milestone_forbidden_for_donor():
    manager = create_user()
    project = create_project(manager["headers"])
    created = create_milestone(manager["headers"], project["id"])
    assert created.status_code == 201, created.text

    donor = create_user("DONOR")
    response = client.patch(
        f"/api/v1/milestones/{created.json()['id']}",
        headers=donor["headers"],
        json={"title": "Unauthorized update"},
    )

    assert response.status_code == 403


def test_delete_milestone():
    manager = create_user()
    project = create_project(manager["headers"])
    created = create_milestone(manager["headers"], project["id"])
    assert created.status_code == 201, created.text

    milestone_id = created.json()["id"]
    response = client.delete(
        f"/api/v1/milestones/{milestone_id}",
        headers=manager["headers"],
    )

    assert response.status_code == 204

    get_response = client.get(
        f"/api/v1/milestones/{milestone_id}",
        headers=manager["headers"],
    )
    assert get_response.status_code == 404
