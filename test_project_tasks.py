
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
from models.volunteer import Volunteer

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
            "title": f"Task Project {uuid4().hex[:6]}",
            "description": "Project created for task testing",
            "start_date": "2026-10-01",
            "status": "ACTIVE",
            "budget": 10000,
            "currency": "INR",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_milestone(headers, project_id):
    response = client.post(
        "/api/v1/milestones",
        headers=headers,
        json={
            "project_id": project_id,
            "title": f"Task milestone {uuid4().hex[:6]}",
            "description": "Milestone for task testing",
            "status": "PENDING",
            "due_date": "2026-12-01T00:00:00Z",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_active_volunteer():
    volunteer_user = create_user("VOLUNTEER")

    profile_response = client.post(
        "/api/v1/volunteers",
        headers=volunteer_user["headers"],
        json={
            "skills": ["Teaching", "Community Outreach"],
            "availability": "FLEXIBLE",
            "hours_per_week": 10,
            "experience_years": 1,
        },
    )
    assert profile_response.status_code == 201, profile_response.text

    volunteer_id = profile_response.json()["id"]

    # Activate the volunteer for the task-assignment tests.
    with SessionLocal() as db:
        volunteer = db.get(Volunteer, volunteer_id)
        assert volunteer is not None
        volunteer.status = "ACTIVE"
        db.commit()

    return volunteer_id


def create_task(headers, project_id, **overrides):
    payload = {
        "project_id": project_id,
        "title": f"Task {uuid4().hex[:6]}",
        "description": "Task test description",
        "priority": "MEDIUM",
        "status": "TODO",
        "start_date": "2026-10-01T00:00:00Z",
        "due_date": "2026-12-01T00:00:00Z",
    }
    payload.update(overrides)

    return client.post(
        "/api/v1/tasks",
        headers=headers,
        json=payload,
    )


def test_create_task_success():
    manager = create_user()
    project = create_project(manager["headers"])
    milestone = create_milestone(manager["headers"], project["id"])

    response = create_task(
        manager["headers"],
        project["id"],
        milestone_id=milestone["id"],
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["project_id"] == project["id"]
    assert data["milestone_id"] == milestone["id"]
    assert data["status"] == "TODO"
    assert data["priority"] == "MEDIUM"


def test_create_task_requires_authentication():
    response = client.post(
        "/api/v1/tasks",
        json={"project_id": 1, "title": "Unauthenticated task"},
    )
    assert response.status_code in (401, 403)


def test_create_task_forbidden_for_donor():
    donor = create_user("DONOR")
    response = create_task(donor["headers"], 1)
    assert response.status_code == 403


def test_create_task_rejects_missing_project():
    manager = create_user()

    response = create_task(
        manager["headers"],
        999999,
        title="Task with missing project",
    )

    assert response.status_code == 404


def test_create_task_rejects_missing_milestone():
    manager = create_user()
    project = create_project(manager["headers"])

    response = create_task(
        manager["headers"],
        project["id"],
        milestone_id=999999,
    )

    assert response.status_code == 404


def test_create_task_rejects_milestone_from_another_project():
    manager = create_user()
    first_project = create_project(manager["headers"])
    second_project = create_project(manager["headers"])
    milestone = create_milestone(
        manager["headers"], first_project["id"]
    )

    response = create_task(
        manager["headers"],
        second_project["id"],
        milestone_id=milestone["id"],
    )

    assert response.status_code == 400


def test_create_task_rejects_invalid_volunteer():
    manager = create_user()
    project = create_project(manager["headers"])

    response = create_task(
        manager["headers"],
        project["id"],
        assigned_volunteer_id=999999,
    )

    assert response.status_code == 404


def test_create_task_with_active_volunteer():
    manager = create_user()
    project = create_project(manager["headers"])
    volunteer_id = create_active_volunteer()

    response = create_task(
        manager["headers"],
        project["id"],
        assigned_volunteer_id=volunteer_id,
    )

    assert response.status_code == 201, response.text
    assert response.json()["assigned_volunteer_id"] == volunteer_id


def test_create_task_rejects_invalid_date_range():
    manager = create_user()
    project = create_project(manager["headers"])

    response = create_task(
        manager["headers"],
        project["id"],
        start_date="2026-12-15T00:00:00Z",
        due_date="2026-10-01T00:00:00Z",
    )

    assert response.status_code == 422


def test_create_task_rejects_invalid_priority():
    manager = create_user()
    project = create_project(manager["headers"])

    response = create_task(
        manager["headers"],
        project["id"],
        priority="EXTREME",
    )

    assert response.status_code == 422


def test_list_tasks():
    manager = create_user()
    project = create_project(manager["headers"])

    first = create_task(manager["headers"], project["id"])
    second = create_task(manager["headers"], project["id"])
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text

    response = client.get(
        "/api/v1/tasks",
        headers=manager["headers"],
        params={"project_id": project["id"]},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_tasks_filters_by_status():
    manager = create_user()
    project = create_project(manager["headers"])

    todo = create_task(
        manager["headers"], project["id"], status="TODO"
    )
    completed = create_task(
        manager["headers"], project["id"], status="COMPLETED"
    )
    assert todo.status_code == 201, todo.text
    assert completed.status_code == 201, completed.text

    response = client.get(
        "/api/v1/tasks",
        headers=manager["headers"],
        params={"project_id": project["id"], "status": "TODO"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "TODO"


def test_list_tasks_supports_pagination():
    manager = create_user()
    project = create_project(manager["headers"])

    for _ in range(3):
        response = create_task(manager["headers"], project["id"])
        assert response.status_code == 201, response.text

    response = client.get(
        "/api/v1/tasks",
        headers=manager["headers"],
        params={"project_id": project["id"], "page": 1, "page_size": 2},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2


def test_get_task_by_id():
    manager = create_user()
    project = create_project(manager["headers"])
    created = create_task(manager["headers"], project["id"])
    assert created.status_code == 201, created.text

    task_id = created.json()["id"]
    response = client.get(
        f"/api/v1/tasks/{task_id}",
        headers=manager["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == task_id


def test_get_missing_task_returns_404():
    manager = create_user()

    response = client.get(
        "/api/v1/tasks/999999",
        headers=manager["headers"],
    )

    assert response.status_code == 404


def test_update_task_status_to_completed():
    manager = create_user()
    project = create_project(manager["headers"])
    created = create_task(manager["headers"], project["id"])
    assert created.status_code == 201, created.text

    task_id = created.json()["id"]
    response = client.patch(
        f"/api/v1/tasks/{task_id}",
        headers=manager["headers"],
        json={"status": "COMPLETED"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["completed_at"] is not None


def test_update_task_title_and_priority():
    manager = create_user()
    project = create_project(manager["headers"])
    created = create_task(manager["headers"], project["id"])
    assert created.status_code == 201, created.text

    task_id = created.json()["id"]
    response = client.patch(
        f"/api/v1/tasks/{task_id}",
        headers=manager["headers"],
        json={
            "title": "Updated community task",
            "priority": "HIGH",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["title"] == "Updated community task"
    assert response.json()["priority"] == "HIGH"


def test_update_task_forbidden_for_donor():
    manager = create_user()
    project = create_project(manager["headers"])
    created = create_task(manager["headers"], project["id"])
    assert created.status_code == 201, created.text

    donor = create_user("DONOR")
    response = client.patch(
        f"/api/v1/tasks/{created.json()['id']}",
        headers=donor["headers"],
        json={"title": "Unauthorized task update"},
    )

    assert response.status_code == 403


def test_delete_task():
    manager = create_user()
    project = create_project(manager["headers"])
    created = create_task(manager["headers"], project["id"])
    assert created.status_code == 201, created.text

    task_id = created.json()["id"]
    response = client.delete(
        f"/api/v1/tasks/{task_id}",
        headers=manager["headers"],
    )

    assert response.status_code == 204

    get_response = client.get(
        f"/api/v1/tasks/{task_id}",
        headers=manager["headers"],
    )
    assert get_response.status_code == 404
